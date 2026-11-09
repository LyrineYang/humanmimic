#!/usr/bin/env python3
"""Package frozen recordings for presentation; never run a policy or simulator."""
import argparse
import concurrent.futures
import csv
import hashlib
import html
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'runs/r4-prerequisites-live-20261103-01'
FONT = 'WenQuanYi Zen Hei'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clock(seconds):
    ticks = round(seconds * 100)
    return '{}:{:02d}:{:02d}.{:02d}'.format(ticks // 360000, ticks // 6000 % 60,
                                          ticks // 100 % 60, ticks % 100)


def event(start, end, text, x, y, size=30, color='FFFFFF'):
    # ASS uses BGR colors. Coordinates refer to a 1600 x 900 canvas.
    bgr = color[4:6] + color[2:4] + color[0:2]
    return ('Dialogue: 0,{},{},Default,,0,0,0,,{{\\an7\\pos({},{})\\fs{}'
            '\\1c&H{}&}}{}\n').format(clock(start), clock(end), x, y, size, bgr, text)


def write_ass(path, lines):
    path.write_text('[Script Info]\nScriptType: v4.00+\nPlayResX: 1600\n'
                    'PlayResY: 900\nWrapStyle: 2\n\n[V4+ Styles]\n'
                    'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, '
                    'OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, '
                    'ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, '
                    'Alignment, MarginL, MarginR, MarginV, Encoding\n'
                    'Style: Default,' + FONT + ',30,&H00FFFFFF,&H00FFFFFF,&H00101824,'
                    '&H00101824,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1\n\n'
                    '[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, '
                    'MarginR, MarginV, Effect, Text\n' + ''.join(lines), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    budget = json.loads((ROOT / 'configs/budget.json').read_text())
    if not budget.get('local_demo_campaign', {}).get('showcase_generation_authorized', False):
        parser.error('Showcase generation is disabled; raw experiment demos are a separate permission')
    out = args.output.resolve()
    if any(c in str(out) for c in "'[],:;\\\n"):
        parser.error('Output path contains unsupported FFmpeg filter characters')
    media = out / 'media'
    media.mkdir(parents=True, exist_ok=False)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    def run(name, args):
        command = [ffmpeg, '-hide_banner', '-loglevel', 'warning', '-nostdin',
                   '-threads', '2', '-filter_threads', '1', *args]
        (out / (name + '-command.json')).write_text(json.dumps(command, indent=2) + '\n')
        with (out / (name + '.log')).open('w') as log:
            subprocess.run(command, stdout=log, stderr=log, check=True)

    encode = ['-c:v', 'libx264', '-preset', 'fast', '-crf', '19', '-pix_fmt',
              'yuv420p', '-threads', '2', '-movflags', '+faststart', '-an']
    specs = [
        ('place', 'physical-u_handle-110-place-calibrated-01/private-evaluation',
         'actual-execution.mp4', '01 / LEAP 抓取、搬移与释放',
         [('最终位置误差', '3.76 mm'), ('最终角度误差', '1.94°'), ('抬升保持', '3.90 s')]),
        ('hold', 'physical-u_handle-110-07-c01/private-evaluation',
         'actual-execution.mp4', '02 / LEAP 抬升与稳定保持',
         [('抬升保持', '7.48 s'), ('最大穿透', '0.95 mm'), ('抬升期间对向接触', '100%')]),
        ('load', 'full-hand-gravity-40', 'full-hand-load.mp4',
         '03 / 完整手加载校准', [('校准试次', '20 拟合 + 20 验证'),
         ('局部顺应性下界', '0.1214 mm/N'), ('证据范围', '已标定局部手姿')]),
        ('touch', 'p1-native-fixed', 'actual-four-pad-execution.mp4',
         '04 / 四指触力传感桥', [('工程检查', '6 项通过'),
         ('已检查', '方向 / 载荷 / 失联'), ('证据范围', '四个远端指节组件')]),
    ]
    items = []
    for key, folder, filename, title, metrics in specs:
        source = BASE / folder / filename
        report = source.with_name('result.json')
        result = json.loads(report.read_text())
        sha = digest(source)
        expected = result.get('artifacts_sha256', {}).get(filename)
        if expected and expected != sha:
            raise ValueError('Source hash mismatch: ' + str(source))
        reader = imageio_ffmpeg.read_frames(str(source))
        meta = next(reader)
        reader.close()
        duration = meta['duration']
        shutil.copyfile(source, media / ('original-' + key + '.mp4'))
        note = ('历史开发参考｜手指载荷超过当前 2 N 界｜不是视频学习或 E3 收益结果'
                if key in ('place', 'hold') else
                '局部传感 / 校准演示｜不代表任意姿态安全，也不代表物体材料标定')
        lines = [event(0, duration, 'HUMANMIMIC  /  SIMULATION DEMO', 40, 20, 22, '72DFC3'),
                 event(0, duration, title, 40, 52, 35),
                 event(0, duration, '原始全程 · 1× 速度', 1040, 125, 28, '72DFC3'),
                 event(0, duration, '真实动力学记录 / 2026-11-03', 1040, 170, 23, 'A9B8CA'),
                 event(0, duration, note, 40, 848, 25, 'F5C77F')]
        for index, (label, value) in enumerate(metrics):
            y = 245 + index * 125
            lines.extend([event(0, duration, label, 1040, y, 25, 'A9B8CA'),
                          event(0, duration, value, 1040, y + 40, 40)])
        if key in ('place', 'hold'):
            with source.with_name('actual-state.csv').open() as stream:
                states = list(csv.DictReader(stream))
            z0 = float(states[0]['object_z'])
            for frame in range(round(duration * meta['fps'])):
                t = frame / meta['fps']
                row = min(states, key=lambda r: abs(float(r['time_s']) - t))
                dz = (float(row['object_z']) - z0) * 1000
                label = '仿真时间  {:5.2f} s\\N物体高度变化  {:+6.1f} mm'.format(t, dz)
                lines.append(event(t, min(t + 1 / meta['fps'], duration), label,
                                   1040, 680, 27, '72DFC3'))
        else:
            lines.append(event(0, duration, '完整原片，未剪去失败片段\\N字幕与调色仅用于展示',
                               1040, 690, 24, 'A9B8CA'))
        subtitle = out / (key + '.ass')
        write_ass(subtitle, lines)
        items.append({'id': key, 'title': title, 'source': str(source.relative_to(ROOT)),
                      'source_sha256': sha, 'original_evaluation_hash_present': bool(expected),
                      'result': str(report.relative_to(ROOT)), 'result_sha256': digest(report),
                      'source_duration_s': duration, 'source_fps': meta['fps'],
                      'metrics': metrics, 'note': note, 'task_status': result.get('task_status'),
                      'file': 'media/' + key + '.mp4', 'subtitle': str(subtitle)})

    def render(item):
        key = item['id']
        video_filter = ('scale=960:720:flags=lanczos,eq=gamma=1.35:brightness=0.025,'
                        'pad=1600:900:40:100:color=0x101824,ass=' + item['subtitle'])
        run(key, ['-i', str(ROOT / item['source']), '-vf', video_filter,
                  *encode, str(media / (key + '.mp4'))])
        return key

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for key in pool.map(render, items):
            print('Rendered:', key, flush=True)

    for name, title, subtitle, body in [
        ('intro', '从看懂动作，到拿稳放准', 'HumanMimic / 现有仿真演示',
         '先展示已有物理执行，再验证模型修正的价值\\N本片为历史开发样例，不是完整视频学习系统'),
        ('outro', '下一步：让模型随操作经验修正', '研究目标 / 尚待验证',
         '视频给初始动作 → 接触修正物体模型 → 任务相关观察\\N当前优先：2 N 内成功抓放、完整置信度校准、E3 对照')]:
        ass = out / (name + '.ass')
        write_ass(ass, [event(0, 3, 'HUMANMIMIC  /  RESEARCH PREVIEW', 100, 165, 28, '72DFC3'),
                        event(0, 3, title, 100, 270, 57),
                        event(0, 3, subtitle, 100, 390, 32, 'F5C77F'),
                        event(0, 3, body, 100, 505, 30, 'A9B8CA')])
        run(name, ['-f', 'lavfi', '-i', 'color=c=0x101824:s=1600x900:r=25:d=3',
                   '-vf', 'ass=' + str(ass), *encode, str(media / (name + '.mp4'))])
    order = ['intro', 'place', 'hold', 'load', 'touch', 'outro']
    concat = out / 'concat.txt'
    concat.write_text(''.join("file '{}'\n".format(media / (name + '.mp4')) for name in order))
    run('showcase', ['-f', 'concat', '-safe', '0', '-i', str(concat), '-c', 'copy',
                     '-movflags', '+faststart', str(media / 'showcase.mp4')])
    run('poster', ['-ss', '8', '-i', str(media / 'showcase.mp4'), '-frames:v', '1',
                   str(media / 'poster.png')])
    shutil.copyfile(ROOT / 'docs/assets/demo-frame.jpg', media / 'r2-preview.jpg')
    shutil.copyfile(ROOT / 'runs/runtime-portability-20261102-01/example-clean-02/comparison.svg',
                    media / 'geometry.svg')
    manifest = {'scope': 'Presentation of existing recordings; no new scientific trials',
                'base_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                'source_date': '2026-11-03', 'generated_date': '2026-11-09',
                'transform': 'Full frame scaled 1.5x; gamma 1.35, brightness +0.025; '
                             'side-panel titles and logged-state readout; full-duration 1x playback',
                'research_gpu_hours': 0, 'r2_full_video_available_here': False,
                'r2_source_creator': 'https://www.youtube.com/watch?v=gRexOgq8h-8',
                'geometry_scope': 'Previously computed analytic CUDA fixture; no physical manipulation',
                'items': [{k: v for k, v in item.items() if k != 'subtitle'} for item in items]}
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')

    cards = ''
    for item in items:
        values = ''.join('<div><span>{}</span><b>{}</b></div>'.format(html.escape(k), html.escape(v))
                         for k, v in item['metrics'])
        cards += ('<article><h2>{}</h2><video controls preload="metadata" src="{}"></video>'
                  '<div class="metrics">{}</div><p class="note">{}</p>'
                  '<details><summary>原始录像与来源</summary><a href="media/original-{}.mp4">'
                  '原始全程 MP4</a><p class="path">{}</p><p class="path">SHA256 {}</p>'
                  '</details></article>').format(item['title'], item['file'], values,
                   html.escape(item['note']), item['id'], html.escape(item['source']), item['source_sha256'])
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>HumanMimic — Demo Showcase</title>
<style>body{margin:0;background:#101824;color:#f4f7fc;font:16px/1.7 system-ui,sans-serif}main{max-width:1200px;margin:auto;padding:48px 24px}a{color:#72dfc3}h1{font-size:clamp(30px,5vw,56px);line-height:1.3;margin:14px 0}h2{font-size:23px}h3{margin-top:0}.eyebrow{letter-spacing:3px;color:#72dfc3}p{color:#b5c3d4}video{display:block;width:100%;border-radius:12px;background:#080d15}.lead{max-width:850px}.hero{margin:30px 0}.actions{display:flex;gap:22px;flex-wrap:wrap}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(440px,1fr));gap:24px}article{background:#182334;padding:22px;border:1px solid #2a3b50;border-radius:18px}.metrics{display:flex;gap:20px;flex-wrap:wrap;padding-top:16px}.metrics span{display:block;color:#a9b8ca;font-size:13px}.metrics b{font-size:24px}.note{color:#f5c77f;font-size:14px}.path{word-break:break-all;font-size:12px}img{max-width:100%;border-radius:8px}.still{background:white}.steps{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin:32px 0}.steps>div{border-top:2px solid #72dfc3;padding-top:18px}details{color:#b5c3d4}footer{margin-top:40px;font-size:13px;color:#a9b8ca}@media(max-width:600px){.grid,.steps{grid-template-columns:1fr}main{padding:25px 15px}}</style>
<main><div class="eyebrow">HUMANMIMIC · SIMULATION ONLY</div><h1>从看懂动作，到拿稳放准。</h1>
<p class="lead">现有演示合集：真实物理抓放、稳定保持与触力校准。字幕指标来自原始记录；展示使用完整时长与原速，仅做亮度调整和排版。研究主线是用操作经验修正物体模型，再把观察用在最影响任务精度的地方。</p>
<div class="actions"><a href="media/showcase.mp4">打开 / 下载演示合集 MP4</a><a href="manifest.json">来源与完整性清单</a></div>
<section class="hero"><video controls preload="metadata" poster="media/poster.png" src="media/showcase.mp4"></video>
<p class="note">抓放与保持来自旧版本开发参考，手指载荷超过当前 2 N 上限。它们证明该条件下可物理执行；当前受限成功参考、视频到策略学习和 E3 收益仍未通过。</p></section>
<div class="grid">''' + cards + '''<article><h2>05 / 视频 → 人形动作模仿</h2><img src="media/r2-preview.jpg" alt="原视频、2D关键点、3D人体和真实G1仿真的历史对照帧">
<p>原4060机器的历史工程结果：R1 10/10；R2保留4/5、调试3/5。本机仅有静态预览，31秒完整对照尚需从原机器取回。</p>
<p class="note">静态预览，不是本轮新运行或完整视频。</p><a href="https://www.youtube.com/watch?v=gRexOgq8h-8">原视频 / 创作者来源</a></article>
<article><h2>06 / 粗模型 → 联合估计</h2><img class="still" src="media/geometry.svg" alt="既有解析例的粗模型与估计表面对照">
<p>独立CUDA解析例：平移RMSE 0.0194mm、形状RMSE 0.0260mm。用于说明估计器输入输出。</p><p class="note">合成解析数据；没有物理操作，不代表真实视频精度，原例置信度尚未通过。</p></article></div>
<h2>接下来怎样快速获得更完整的演示</h2><div class="steps"><div><h3>现在：已有结果呈现</h3><p>保留完整动作，加可读指标、原始来源和清晰状态。取回R2完整录像后补进合集。</p></div><div><h3>短线：复现预训练技能</h3><p>优先检查DexTrack的LEAP跟踪样例，或ViViDex预训练搬移。成功只按该方法、该手型和原任务条件报告。</p></div><div><h3>主线：让经验改善精度</h3><p>补齐2N抓放与全状态校准，固定参考和控制器，在同预算下验证局部几何与任务相关探触。</p></div></div>
<footer>生成于2026-11-09 · 所有视频来自既有本地运行 · 未启动训练或新仿真 · 该包不包含受限MANO资产和模型权重。状态与来源见manifest.json。</footer></main></html>'''
    (out / 'index.html').write_text(page, encoding='utf-8')
    validation = []
    for path in sorted(media.glob('*.mp4')):
        frames = imageio_ffmpeg.count_frames_and_secs(str(path))
        validation.append({'file': str(path.relative_to(out)), 'frames': frames[0],
                           'duration_s': frames[1], 'sha256': digest(path)})
    by_name = {v['file']: v for v in validation}
    checks = {'selected_sources_fully_preserved': all(
        by_name[item['file']]['frames'] == by_name['media/original-' + item['id'] + '.mp4']['frames']
        and abs(by_name[item['file']]['duration_s'] - item['source_duration_s']) < .06
        for item in items), 'all_videos_decode': all(v['frames'] > 0 for v in validation)}
    (out / 'media-check.json').write_text(json.dumps({'status': 'passed' if all(checks.values()) else 'failed',
        'checks': checks, 'files': validation}, indent=2) + '\n')
    if not all(checks.values()):
        raise RuntimeError('Video validation failed')
    with zipfile.ZipFile(out / 'HumanMimic-demo.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in [out / 'index.html', out / 'manifest.json', out / 'media-check.json', *media.iterdir()]:
            archive.write(path, path.relative_to(out))
    print(json.dumps({'status': 'passed', 'output': str(out), 'clips': len(items),
                      'showcase_duration_s': by_name['media/showcase.mp4']['duration_s']}), flush=True)


if __name__ == '__main__':
    main()
