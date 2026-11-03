"""Trusted hand-only export and CUDA forward kinematics / damped IK.

The exporter never exports object, contacts, materials or a simulator pointer.
All optimization uses the serialized LEAP chain below in the worker process.
"""
import torch
from r4_belief import skew
from r4_contract import JOINT_NAMES
from r4_public import keys


def export_hand(model):
    import mujoco
    joints = {mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name): i for i, name in enumerate(JOINT_NAMES)}
    palm = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "palm")
    chains = {}
    for finger in ["if", "mf", "rf", "th"]:
        site = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, f"r4_{finger}_sensor")
        if site < 0:
            raise ValueError("Instrument LEAP before exporting known hand kinematics")
        body, chain = int(model.site_bodyid[site]), []
        while body != palm:
            if body == 0:
                raise ValueError("Finger is not rooted at the declared palm")
            description = {"position": model.body_pos[body].tolist(), "quaternion": model.body_quat[body].tolist(), "joints": []}
            for j in range(int(model.body_jntadr[body]), int(model.body_jntadr[body]+model.body_jntnum[body])):
                if j not in joints or model.jnt_type[j] != mujoco.mjtJoint.mjJNT_HINGE:
                    raise ValueError("Only known LEAP hinge joints may enter hand model")
                description["joints"].append({"index": joints[j], "axis": model.jnt_axis[j].tolist(),
                    "pivot": model.jnt_pos[j].tolist(), "reference": float(model.qpos0[model.jnt_qposadr[j]])})
            chain.insert(0, description)
            body = int(model.body_parentid[body])
        chains[finger] = {"bodies": chain, "site_position": model.site_pos[site].tolist(), "site_quaternion": model.site_quat[site].tolist()}
    ranges = [None]*16
    for j, index in joints.items():
        ranges[index] = model.jnt_range[j].tolist()
    return {"role": "known_hand_kinematics", "hand": "leap_right", "joint_names": JOINT_NAMES, "ranges": ranges, "chains": chains}


def rotation(q):
    q = q/q.norm()
    w, x, y, z = q.unbind()
    return torch.stack([1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w), 2*(x*y+z*w), 1-2*(x*x+z*z),
                        2*(y*z-x*w), 2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]).reshape(3, 3)


class HandModel:
    def __init__(self, specification, device):
        if device.type != "cuda":
            raise RuntimeError("Hand planning requires CUDA")
        keys(specification, {"role", "hand", "joint_names", "ranges", "chains"})
        if specification["role"] != "known_hand_kinematics" or specification["joint_names"] != JOINT_NAMES or specification["hand"] != "leap_right":
            raise ValueError("Invalid known hand model")
        self.spec, self.device = specification, device
        self.ranges = self.tensor(specification["ranges"])
        self.identity = torch.eye(3, device=device, dtype=torch.float64)
        self.chains = []
        for finger in ["if", "mf", "rf", "th"]:
            chain = specification["chains"][finger]
            bodies = []
            for body in chain["bodies"]:
                joints = []
                for joint in body["joints"]:
                    axis = self.tensor(joint["axis"])
                    k = skew(axis/axis.norm())
                    joints.append((joint["index"], joint["reference"], self.tensor(joint["pivot"]), k, k@k))
                bodies.append((self.tensor(body["position"]), rotation(self.tensor(body["quaternion"])), joints))
            self.chains.append((bodies, self.tensor(chain["site_position"]), rotation(self.tensor(chain["site_quaternion"]))))

    def tensor(self, value):
        return torch.as_tensor(value, device=self.device, dtype=torch.float64)

    def forward(self, q, wrist):
        """Accept [...,16] joint arrays; fixed chain tensors stay on the GPU."""
        frames = []
        for bodies, site_position, site_rotation in self.chains:
            r = wrist[..., :3, :3].expand(*q.shape[:-1], 3, 3)
            p = wrist[..., :3, 3].expand(*q.shape[:-1], 3)
            for position, fixed_rotation, joints in bodies:
                p = p + r@position
                r = r@fixed_rotation
                for index, reference, pivot, k, k2 in joints:
                    angle = (q[..., index]-reference)[..., None, None]
                    turn = self.identity+angle.sin()*k+(1-angle.cos())*k2
                    p = p + (r@(pivot-turn@pivot)[..., None]).squeeze(-1)
                    r = r@turn
            p = p+r@site_position
            r = r@site_rotation
            transform = torch.eye(4, device=self.device, dtype=q.dtype).expand(*q.shape[:-1], 4, 4).clone()
            transform[..., :3, :3], transform[..., :3, 3] = r, p
            frames.append(transform)
        return torch.stack(frames, dim=-3)

    def position_jacobian(self,q,wrist,points_world=None):
        """Analytic world translation Jacobian of known hand sensor sites, CUDA."""
        if q.shape!=(16,) or wrist.shape!=(4,4):raise ValueError('Single known hand state required')
        rows=[]
        for finger,(bodies,site_position,_) in enumerate(self.chains):
            r=wrist[:3,:3];p=wrist[:3,3];axes=[]
            for position,fixed_rotation,joints in bodies:
                p=p+r@position;r=r@fixed_rotation
                for index,reference,pivot,k,k2 in joints:
                    axis=torch.stack([k[2,1],k[0,2],k[1,0]])
                    axes.append((index,r@axis,p+r@pivot))
                    angle=q[index]-reference;turn=self.identity+angle.sin()*k+(1-angle.cos())*k2
                    p=p+r@(pivot-turn@pivot);r=r@turn
            tip=p+r@site_position if points_world is None else points_world[finger]
            jac=torch.zeros((3,16),device=self.device,dtype=q.dtype)
            for index,axis,origin in axes:jac[:,index]=torch.linalg.cross(axis,tip-origin)
            rows.append(jac)
        return torch.stack(rows)

    def ik(self, reference, wrist, targets, limit=.06, iterations=4):
        q = reference.detach().clone()
        for _ in range(iterations):
            q.requires_grad_(True)
            function = lambda value: self.forward(value, wrist)[:, :3, 3].reshape(-1)
            current = function(q)
            jac = torch.autograd.functional.jacobian(function, q, vectorize=True)
            delta = jac.T@torch.linalg.solve(jac@jac.T+torch.eye(12, device=self.device, dtype=q.dtype)*1e-5, targets.reshape(-1)-current)
            q = torch.maximum(torch.minimum((q+delta).detach(), reference+limit), reference-limit)
            q = torch.maximum(torch.minimum(q, self.ranges[:, 1]), self.ranges[:, 0])
        return q
