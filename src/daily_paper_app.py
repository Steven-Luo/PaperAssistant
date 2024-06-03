"""
 Created by luogang on 2024/2/29
"""
import os
from pathlib import Path
import sys

import common_utils

sys.path.append(str(Path(__file__).parent.parent.resolve()))

from service.arxiv_visitor import ArxivVisitor
from service.hf_visotor import HFDailyPaperVisitor
from tqdm import tqdm

from service.notion_service import NotionService


def main(dt=None):
    output_root = os.path.join(Path(__file__).parent.parent.resolve(), 'output')
    os.makedirs(os.path.join(output_root, 'cache'), exist_ok=True)

    hf_visitor = HFDailyPaperVisitor(output_root, dt=dt)
    create_dt = hf_visitor.datetime.strftime('%Y-%m-%d')
    ckpt_filename = os.path.join(output_root, "cache", f"ckpt_{create_dt}.txt")
    ckpt_file = open(ckpt_filename, 'a')
    ckpt = set()
    if os.path.exists(ckpt_filename):
        ckpt = set([line.strip() for line in open(ckpt_filename, 'r').readlines() if line.strip() != ''])

    arxiv_visitor = ArxivVisitor(output_dir=output_root)
    notion_service = NotionService(create_time=hf_visitor.datetime)
    for hf_obj in tqdm(hf_visitor.paper_list, desc=create_dt):
        if hf_obj['id'] in ckpt:
            continue
        arxiv_obj = arxiv_visitor.find_by_id(hf_obj['id'])
        notion_service.insert(hf_obj, arxiv_obj)
        ckpt.add(hf_obj['id'])
        ckpt_file.write(hf_obj['id'])
        ckpt_file.write('\n')

    if len(hf_visitor.paper_list) > 0:
        common_utils.send_slack(f'更新文章{len(hf_visitor.paper_list)}篇')

if __name__ == '__main__':
    # for dt in ('2024-02-23', '2024-02-24', '2024-02-25', '2024-02-26', '2024-02-27', '2024-02-28', '2024-02-29', '2024-03-01'):
    #     main(dt)
    main()
