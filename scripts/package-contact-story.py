#!/usr/bin/env python3
"""Create a story from measured contact runs and an optional pretrained clip."""
import argparse
import csv
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

import imageio_ffmpeg

spec=importlib.util.spec_from_file_location('demo_style',Path(__file__).with_name('package-r4-demo.py'))
style=importlib.util.module_from_spec(spec);spec.loader.exec_module(style)
event,write_ass=style.event,style.write_ass


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--pretrained',type=Path)
    args=p.parse_args()
    budget=Path(__file__).resolve().parents[1]/'configs/budget.json'
    if not json.loads(budget.read_text())['local_demo_campaign'].get('showcase_generation_authorized',False):
        p.error('Current user instruction disables video generation; preserve existing media and data')
    source=args.run.resolve();out=args.output.resolve()
    media=out/'media';media.mkdir(parents=True,exist_ok=False)
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    encode=['-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart','-an']
    sources={}

    def run(name,command):
        argv=[ffmpeg,'-hide_banner','-loglevel','warning','-nostdin','-threads','2','-filter_threads','1','-filter_complex_threads','1',*command]
        (out/(name+'-command.json')).write_text(json.dumps(argv,indent=2)+'\n')
        with (out/(name+'.log')).open('w') as stream:subprocess.run(argv,stdout=stream,stderr=stream,check=True)

    def use(path):
        sources[str(path)]=style.digest(path)
        return path

    def meta(path):
        reader=imageio_ffmpeg.read_frames(str(path));m=next(reader);reader.close();return m

    def card(name,duration,title,subtitle,body):
        ass=out/(name+'.ass')
        write_ass(ass,[event(0,duration,'HUMANMIMIC  /  从动作到精度',90,125,25,'72DFC3'),
                      event(0,duration,title,90,235,51),event(0,duration,subtitle,90,360,31,'F5C77F'),
                      event(0,duration,body,90,470,32,'B4C2D5')])
        run(name,['-f','lavfi','-i',f'color=c=0x101824:s=1600x900:r=25:d={duration}',
                  '-vf','ass='+str(ass),*encode,str(media/(name+'.mp4'))])

    result=json.loads(use(source/'demo-final/result.json').read_text())
    validation=json.loads(use(source/'verification-summary.json').read_text())
    base=result['baseline'];correct=result['corrected'];reuse=result['reused']
    card('intro',4,'动作可以模仿，精度需要记住','一个小问题：手到了，物体为什么还没放准？',
         '已有技能负责把动作做出来。\\N我们的切口：用一次接触，校正物体边缘到手的距离。')
    order=['intro']
    if args.pretrained:
        pre=args.pretrained.resolve();report=json.loads(use(pre/'result.json').read_text())
        ep=report['episodes'][0];clip=use(pre/ep['video']);duration=meta(clip)['duration']*2+2
        shutil.copyfile(clip,media/'pretrained-original.mp4')
        ass=out/'pretrained.ass'
        write_ass(ass,[event(0,duration,'01 / 复现：先让动作发生',40,45,40),
                      event(0,duration,'ViViDex · 公开预训练状态策略',1040,160,26,'72DFC3'),
                      event(0,duration,'Adroit / sugar box\\N本机 CUDA 推理 / 无训练\\N0.5× 慢放 + 末帧定格',1040,230,28),
                      event(0,duration,'该回合终点误差',1040,370,27,'A9B8CA'),
                      event(0,duration,f'{ep["final_position_error_m"]*1000:.1f} mm',1040,420,44),
                      event(0,duration,'动作底座已运行\\N下段校正仍是独立测试台',1040,560,27,'F5C77F'),
                      event(0,duration,'使用仿真特权状态；未接入新视频、视觉策略或本项目接触校正；释放未验收',40,850,24,'F5C77F')])
        run('pretrained',['-i',str(clip),'-vf','setpts=2*PTS,fps=25,tpad=stop_mode=clone:stop_duration=2,scale=960:720,pad=1600:900:40:100:color=0x101824,ass='+str(ass),
                          '-r','25',*encode,str(media/'pretrained.mp4')])
        order.append('pretrained')
    card('question',4,'只把手移动准确，还不够','物体在手里偏了 8 mm，照原终点放置就会偏 8 mm。',
         '两组使用同一测试台、同一控制器、同一次轻触。\\N唯一差别：接触之后，是否修正物体模型？')
    order.append('question')
    left=use(source/'demo-final/force-only/execution.mp4')
    right=use(source/'demo-final/contact-corrected/execution.mp4')
    duration=meta(left)['duration']
    ass=out/'comparison.ass'
    lines=[event(0,duration,'02 / 碰到就停 → 碰过之后记住偏差',40,30,40),
           event(0,duration,'A  直接力反馈：只退让',40,112,32,'F5C77F'),
           event(0,duration,'B  同一接触：更新模型，再放置',840,112,32,'72DFC3'),
           event(0,duration,f'最终物体边缘误差  {base["final_edge_error_mm"]:.2f} mm',40,755,32,'F5C77F'),
           event(0,duration,f'最终物体边缘误差  {correct["final_edge_error_mm"]:.3f} mm',840,755,32,'72DFC3'),
           event(0,duration,'受控真实动力学｜已稳定夹持由固定约束提供；简化夹持器，不是 LEAP 或学习策略',40,850,23,'F5C77F')]
    with use(source/'demo-final/contact-corrected/public-observations.csv').open() as stream:rows=list(csv.DictReader(stream))
    phase_names={'settle':'稳定','probe':'轻触基准面','withdraw':'退让','transport':'搬移','place':'放置','release':'释放'}
    for i in range(round(duration*25)):
        t=i/25;row=min(rows,key=lambda r:abs(float(r['time_s'])-t))
        measured=row['estimate_valid']=='True'
        text=f't = {t:4.2f} s    {phase_names.get(row["phase"],row["phase"])}    手部力 {float(row["wrist_force_x_n"]):.2f} N'
        lines.append(event(t,min(t+.04,duration),text,40,800,23,'A9B8CA'))
        lines.append(event(t,min(t+.04,duration),('已估计边缘距离  '+f'{float(row["estimate_m"])*1000:.2f} mm') if measured else '粗模型边缘距离  25.00 mm',840,800,23,'A9B8CA'))
    write_ass(ass,lines)
    graph=f'[0:v]scale=720:540,pad=1600:900:40:195:color=0x101824[l];[1:v]scale=720:540[r];[l][r]overlay=840:195,ass={ass}[out]'
    run('comparison',['-i',str(left),'-i',str(right),'-filter_complex',graph,'-map','[out]',*encode,str(media/'comparison.mp4')])
    order.append('comparison')
    clip=use(source/'demo-final/memory-reused/execution.mp4');duration=meta(clip)['duration']
    ass=out/'reuse.ass'
    write_ass(ass,[event(0,duration,'03 / 换一个目标，复用已经知道的偏差',40,45,38),
                  event(0,duration,'记忆保存的是什么？',1040,150,30,'72DFC3'),
                  event(0,duration,f'手到物体边缘\\N{reuse["memory"]["mean_m"]*1000:.2f} mm',1040,220,35),
                  event(0,duration,'本次新增探触：0 次',1040,380,32,'72DFC3'),
                  event(0,duration,f'最终误差 {reuse["final_edge_error_mm"]:.3f} mm',1040,450,32),
                  event(0,duration,'成立条件：夹持关系不变\\N换抓法 / 滑移 → 记忆失效',1040,600,26,'F5C77F'),
                  event(0,duration,'固定夹持关系的重置对照；不是连续重新抓取泛化。完整原速录像。',40,850,24,'F5C77F')])
    run('reuse',['-i',str(clip),'-vf','pad=1600:900:40:100:color=0x101824,ass='+str(ass),*encode,str(media/'reuse.mp4')])
    order.append('reuse')
    card('evidence',6,'不是只选一个好看的成功片段','6 个预先冻结的开发验证条件，全部报告；现已标为使用过。',
         f'平均误差：{validation["baseline_mean_mm"]:.2f} → {validation["corrected_mean_mm"]:.3f} mm\\N'
         f'修正后最大误差：{validation["corrected_max_mm"]:.3f} mm    探触峰值：{validation["contact_peak_max_n"]:.2f} N\\N'
         '范围：已知平面、固定夹持、单方向偏差；不是完整 E3 结果。')
    order.append('evidence')
    card('outro',5,'先学动作，再校准最后几毫米','当前成果：一个可复跑、可解释的局部纠错切片。',
         '下一步：把接触校正接到预训练技能的放置阶段。\\N再比较何时值得探触，何时可以直接复用记忆。\\N最终看物体是否拿稳、放准。')
    order.append('outro')
    concat=out/'concat.txt';concat.write_text(''.join(f"file '{media/(x+'.mp4')}'\n" for x in order))
    run('story',['-f','concat','-safe','0','-i',str(concat),'-c','copy','-movflags','+faststart',str(media/'story.mp4')])
    run('poster',['-ss',str(max(0,meta(media/'comparison.mp4')['duration']-1)),'-i',str(media/'comparison.mp4'),'-frames:v','1',str(media/'poster.png')])
    checks=[]
    for clip in media.glob('*.mp4'):
        run('decode-'+clip.stem,['-i',str(clip),'-f','null','-'])
        n,secs=imageio_ffmpeg.count_frames_and_secs(str(clip))
        checks.append({'file':str(clip.relative_to(out)),'frames':n,'seconds':secs,'sha256':style.digest(clip)})
    (out/'manifest.json').write_text(json.dumps({'scope':'Measured local diagnostic + separately labelled pretrained skill',
        'sources_sha256':sources,'chapters':order,'validation':{k:v for k,v in validation.items() if k!='rows'},'media_checks':checks},ensure_ascii=False,indent=2)+'\n')
    (out/'index.html').write_text('''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HumanMimic · 校准最后几毫米</title><style>body{background:#101824;color:#e9f0f8;font:18px/1.7 system-ui;max-width:1100px;margin:40px auto;padding:20px}h1{font-size:40px}a{color:#72dfc3}video{width:100%;border-radius:14px}small{color:#f5c77f}.cards{display:grid;grid-template-columns:1fr 1fr;gap:24px}</style>
<p>HUMANMIMIC / STORY DEMO</p><h1>动作可以模仿，精度需要记住。</h1>
<p>工程问题：同样的腕部动作，因为物体边缘到手的距离不准，放置仍会偏。一次轻触能否修正它？</p>
<video controls preload="metadata" poster="media/poster.png" src="media/story.mp4"></video>
<p><a href="media/story.mp4">完整故事 MP4</a> · <a href="manifest.json">来源与检查</a></p>
<div class="cards"><section><h2>同条件对照</h2><video controls src="media/comparison.mp4"></video></section><section><h2>有效记忆复用</h2><video controls src="media/reuse.mp4"></video></section></div>
<p><small>局部纠错演示使用固定夹持约束、已知基准面和简化夹持器。预训练复现若出现，属于单独章节，尚未与此校正模块接通。所有指标来自本机记录；不是正式LEAP/E3验收。</small></p></html>''')
    with zipfile.ZipFile(out/'HumanMimic-contact-story.zip','w',zipfile.ZIP_DEFLATED) as z:
        for path in [out/'index.html',out/'manifest.json',*media.iterdir()]:z.write(path,path.relative_to(out))
    print(json.dumps({'video':str(media/'story.mp4'),'duration_s':meta(media/'story.mp4')['duration'],'zip':str(out/'HumanMimic-contact-story.zip')}),flush=True)


if __name__=='__main__':main()
