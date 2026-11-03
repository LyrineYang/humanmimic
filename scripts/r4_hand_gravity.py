"""Trusted low-level gravity feedforward from a separate known-hand model.

No manipulated object or task geometry exists in this model. This is MuJoCo
hand dynamics, not CUDA inference; it never exports simulator truth to P2.
"""
import xml.etree.ElementTree as ET
import mujoco
import numpy as np
from r4_contract import JOINT_NAMES

class HandGravity:
    def __init__(self,asset):
        root=ET.parse(asset/'right_hand.xml').getroot()
        root.find('compiler').set('meshdir',str((asset/'assets').resolve()))
        palm=root.find("worldbody/body[@name='palm']");palm.set('pos','0 0 0');palm.set('quat','1 0 0 0')
        self.model=mujoco.MjModel.from_xml_string(ET.tostring(root,encoding='unicode'))
        self.model.opt.disableflags |= int(mujoco.mjtDisableBit.mjDSBL_CONTACT)
        self.data=mujoco.MjData(self.model)
        joints=np.array([mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_JOINT,n) for n in JOINT_NAMES])
        actuators=np.array([mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_ACTUATOR,n+'_act') for n in JOINT_NAMES])
        self.qadr=self.model.jnt_qposadr[joints];self.dadr=self.model.jnt_dofadr[joints]
        self.gain=self.model.actuator_gainprm[actuators,0].copy()
        if np.any(self.gain<=0):raise ValueError('Positive hand position actuator gain required')
        self.ctrlrange=self.model.actuator_ctrlrange[actuators].copy()

    def target(self,desired,measured,world_rotation):
        self.model.opt.gravity[:]=np.asarray(world_rotation).T@np.array([0.,0.,-9.81])
        self.data.qpos[self.qadr]=measured
        self.data.qvel[:]=0
        mujoco.mj_forward(self.model,self.data)
        compensated=np.asarray(desired)+self.data.qfrc_bias[self.dadr]/self.gain
        return np.clip(compensated,self.ctrlrange[:,0],self.ctrlrange[:,1])
