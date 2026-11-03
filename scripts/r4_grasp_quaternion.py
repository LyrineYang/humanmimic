"""CUDA rotation-matrix to scalar-first unit quaternion (including pi rotations)."""
import torch


def matrix_quaternion(r):
    values=torch.stack([1+r[0,0]+r[1,1]+r[2,2],1+r[0,0]-r[1,1]-r[2,2],
                        1-r[0,0]+r[1,1]-r[2,2],1-r[0,0]-r[1,1]+r[2,2]]).clamp_min(0).sqrt()
    candidates=torch.stack([torch.stack([values[0]**2,r[2,1]-r[1,2],r[0,2]-r[2,0],r[1,0]-r[0,1]]),
        torch.stack([r[2,1]-r[1,2],values[1]**2,r[1,0]+r[0,1],r[0,2]+r[2,0]]),
        torch.stack([r[0,2]-r[2,0],r[1,0]+r[0,1],values[2]**2,r[2,1]+r[1,2]]),
        torch.stack([r[1,0]-r[0,1],r[0,2]+r[2,0],r[2,1]+r[1,2],values[3]**2])])
    q=candidates[values.argmax()];q=q/q.norm()
    return q if q[0]>=0 else -q
