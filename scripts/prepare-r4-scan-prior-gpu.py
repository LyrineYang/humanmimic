#!/usr/bin/env python3
"""CUDA oriented-point surface reconstruction from public multiview RGB-D.

The scan rig is upright. Its observed lower envelope is placed on the known
support plane. No private object pose, CAD or collision parts are read.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import torch
from r4_contract import sha256, write_json
from r4_cuda import require_cuda
from r4_public import validate_prior

def surface(points,normals,resolution):
    device=points.device
    low=points.amin(0)-.006;high=points.amax(0)+.006
    axes=[torch.linspace(low[k],high[k],resolution,device=device,dtype=points.dtype) for k in range(3)]
    grid=torch.stack(torch.meshgrid(*axes,indexing='ij'),-1).reshape(-1,3)
    nearest=[]
    for chunk in grid.split(256):nearest.append(torch.cdist(chunk,points).argmin(1))
    nearest=torch.cat(nearest);distance=((grid-points[nearest])*normals[nearest]).sum(-1)
    corners=torch.tensor([[0,0,0],[1,0,0],[1,1,0],[0,1,0],[0,0,1],[1,0,1],[1,1,1],[0,1,1]],device=device)
    base=torch.stack(torch.meshgrid(*[torch.arange(resolution-1,device=device)]*3,indexing='ij'),-1).reshape(-1,3)
    ids=(base[:,None]+corners);ids=(ids[:,:,0]*resolution+ids[:,:,1])*resolution+ids[:,:,2]
    tetra=torch.tensor([[0,1,2,6],[0,2,3,6],[0,3,7,6],[0,7,4,6],[0,4,5,6],[0,5,1,6]],device=device)
    cells=ids[:,tetra].reshape(-1,4)
    bits=(distance[cells]<0).long();code=(bits*torch.tensor([1,2,4,8],device=device)).sum(-1)
    edge_pairs=torch.tensor([[0,1],[0,2],[0,3],[1,2],[1,3],[2,3]],device=device)
    # Unoriented marching tetrahedra; normals below orient all emitted triangles.
    table={1:[[0,1,2]],2:[[0,3,4]],3:[[1,2,3],[2,4,3]],4:[[1,3,5]],5:[[0,2,3],[2,5,3]],
           6:[[0,1,4],[1,5,4]],7:[[2,4,5]]}
    edges=[]
    for code_value,tris in table.items():
        chosen=cells[(code==code_value)|(code==15-code_value)]
        pairs=edge_pairs[torch.tensor(tris,device=device)]
        edges.append(chosen[:,pairs].reshape(-1,3,2))
    edge_ids=torch.cat(edges).sort(-1).values
    unique,inverse=torch.unique(edge_ids.reshape(-1,2),dim=0,return_inverse=True)
    a,b=unique.unbind(-1);weight=distance[a]/(distance[a]-distance[b])
    vertices=grid[a]+weight[:,None]*(grid[b]-grid[a]);faces=inverse.reshape(-1,3)
    indices=torch.cat([torch.cdist(chunk,points).argmin(1) for chunk in vertices.split(256)])
    vn=normals[indices]
    tri=vertices[faces];cross=torch.linalg.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
    reverse=(cross*vn[faces].mean(1)).sum(-1)<0
    faces[reverse]=faces[reverse][:,[0,2,1]]
    return vertices,vn,faces

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--observations',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--resolution',type=int,default=16)
    args=p.parse_args();device,gpu=require_cuda()
    raw=np.load(args.observations,allow_pickle=False)
    points=torch.as_tensor(raw['points'],device=device,dtype=torch.float64)
    normals=torch.as_tensor(raw['normals'],device=device,dtype=torch.float64)
    # Deterministic sensor sampling, same input for every comparison.
    index=torch.linspace(0,len(points)-1,min(len(points),8192),device=device).long()
    points,normals=points[index],normals[index]
    if not bool(torch.isfinite(points).all() & torch.isfinite(normals).all()):raise ValueError('Nonfinite scan')
    normals=normals/normals.norm(dim=-1,keepdim=True).clamp_min(1e-12)
    vertices,vn,faces=surface(points,normals,args.resolution)
    if len(vertices)>2048 or len(vertices)<32:raise ValueError('Prior vertex budget exceeded; choose documented coarser resolution')
    transform=torch.eye(4,device=device,dtype=torch.float64);transform[2,3]=-torch.quantile(points[:,2],.001)+.001
    prior={'schema_version':2,'role':'coarse_estimate','source':'observed_rgbd','vertices_object_m':vertices.tolist(),
        'normals_object':vn.tolist(),'faces':faces.tolist(),'roi_vertex_indices':list(range(len(vertices))),
        'T_world_object_initial':transform.tolist(),'initial_time_s':0.,'compliance_initial_m_per_n':.0001}
    validate_prior(prior);args.output.mkdir(parents=True,exist_ok=False);write_json(args.output/'prior.json',prior)
    write_json(args.output/'manifest.json',{'execution_status':'completed','status':'awaiting_verification','gpu':gpu,
        'vertices':len(vertices),'faces':len(faces),'resolution':args.resolution,'observations_sha256':sha256(args.observations),
        'source_sha256':sha256(__file__),'heldout_used':False,'coordinate_gauge':'observed scan frame; evaluate relative motion with frozen initial alignment',
        'limitation':'Nearest oriented-point field may create unsupported surfaces; no reconstruction or operation accuracy claim'})

if __name__=='__main__':main()
