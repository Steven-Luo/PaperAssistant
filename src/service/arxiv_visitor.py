"""
 Created by luogang on 2024/2/29
"""
import json
import os
import pickle
import re
from typing import Union, List
from urllib.request import urlretrieve

import arxiv

import common_utils
from entity.formatted_arxiv_obj import FormattedArxivObj
from service import llm_service

logger = common_utils.get_logger(__name__)


def extract_json(ret_json_str):
    try:
        parsed_ret = ret_json_str.replace('```json\n', '').replace('\n```', '')
        parsed_ret = json.loads(parsed_ret)
    except Exception as e:
        print(e)
        json_pattern = r'\{.*?\}'
        parsed_ret = re.findall(json_pattern, ret_json_str, re.DOTALL)[0]
        parsed_ret = json.loads(parsed_ret)
    return parsed_ret


class ArxivVisitor:
    def __init__(self, output_dir, page_size=10, disable_cache=False):
        self.cache_dir = os.path.join(output_dir, 'cache')
        os.makedirs(self.cache_dir, exist_ok=True)
        self.client = arxiv.Client(page_size=page_size)

    def _process_tldr(self, summary, cache_obj, cache_filename):
        logger.info(f"processing tldr for {cache_obj['id']}")

        keys = ('动机', '方法', '结果')
        if 'tldr' in cache_obj and all([key in cache_obj['tldr'] and cache_obj['tldr'][key].strip() != '' for key in keys]):
            logger.info(f"processing tldr found cache")
            return

        if 'raw_tldr' in cache_obj and cache_obj['raw_tldr'].strip() != '':
            tldr = cache_obj['raw_tldr']
        else:
            tldr = llm_service.chat(
                f'下面这段话（<summary></summary>之间的部分）是一篇论文的摘要，请基于摘要信息总结论文的动机、方法、结果，请使用中文表述，结果请输出三行，分别以“动机“、“方法”、“结果”开头，与对应的值使用制表符“\\t”分割，如果某一项不存在，请输出空字符串，请认真回答，如果回答的好我会给你很多小费：\n<summary>{summary}</summary>')
            cache_obj['raw_tldr'] = tldr
        try:
            parsed_tldr = {}
            for line in tldr.split('\n'):
                if line.strip() == '':
                    continue
                parts = line.split('\t')
                parsed_tldr.update({parts[0]: '\t'.join(parts[1:]).replace('\\t', '\t').strip()})
        except Exception as e:
            logger.error(e)

        if 'tldr' not in cache_obj:
            cache_obj['tldr'] = {}

        cache_obj['tldr'].update(parsed_tldr)
        for key in keys:
            if key not in cache_obj['tldr']:
                logger.warning(f"{key} not int parsed tldr")
                cache_obj['tldr'][key] = ''
        json.dump(cache_obj, open(cache_filename, 'w'), ensure_ascii=False, indent=2)

    def _process_summary(self, summary, cache_obj, cache_filename):
        logger.info(f"processing summary for {cache_obj['id']}")
        if 'summary_cn' in cache_obj:
            logger.info(f"processing summary found cache")
            return
        summary_cn = llm_service.chat(f'这段话是一篇论文的摘要，请把它翻译为中文：\n{summary}')
        cache_obj['summary_cn'] = summary_cn
        json.dump(cache_obj, open(cache_filename, 'w'), ensure_ascii=False, indent=2)

    def _process_tag_info(self, summary, cache_obj, cache_filename):
        logger.info(f"processing tag info for {cache_obj['id']}")

        keys = ('主要领域', '标签')
        if 'tag_info' in cache_obj and all([key in cache_obj['tag_info'] for key in keys]):
            logger.info(f"processing tags info found cache")
            return
        # ```json
        # {
        #   "主要领域": "NLP",
        #   "标签": [
        #     "instruction-tuning",
        #     "language models",
        #     "training data selection",
        #     "learning percentage",
        #     "data hardness",
        #     "model sizes",
        #     "OPT",
        #     "Llama-2"
        #   ]
        # }
        # ```
        if 'tag_info_raw' in cache_obj and cache_obj['tag_info_raw'].strip() != '':
            tag_info = cache_obj['tag_info_raw']
        else:
            tag_info = llm_service.chat(
                f'这段话是一篇论文的摘要，请基于摘要信息判断这篇论文的主要领域，例如NLP、多模态、CV、Machine Learning等，并提取标签，结果请使用JSON形式组织\n{summary}')
            cache_obj['tag_info_raw'] = tag_info

        try:
            parsed_tag_info = extract_json(tag_info)
        except Exception as e:
            logger.error(e)
        if 'tag_info' not in cache_obj:
            cache_obj['tag_info'] = {}

        if '主要领域' in parsed_tag_info and isinstance(parsed_tag_info['主要领域'], list):
            parsed_tag_info['主要领域'] = parsed_tag_info['主要领域'][0] if len(parsed_tag_info['主要领域']) > 0 else ''

        cache_obj['tag_info'].update(parsed_tag_info)
        if '主要领域' not in cache_obj['tag_info']:
            cache_obj['tag_info']['主要领域'] = ''
        if '标签' not in cache_obj['tag_info']:
            cache_obj['tag_info']['标签'] = []
        json.dump(cache_obj, open(cache_filename, 'w'), ensure_ascii=False, indent=2)

    def _post_process(self, arxiv_result, hf_obj=None):
        summary = arxiv_result.summary.replace('\n', ' ').replace('  ', ' ')
        _id = arxiv_result.entry_id.split('/')[-1]
        cache_obj = {
            'id': _id,
            'title': arxiv_result.title,
            'pdf_url': arxiv_result.pdf_url
        }
        if hf_obj is not None:
            cache_obj['media_type'] = hf_obj['media_type']
            cache_obj['media_url'] = hf_obj['media_url']

        cache_filename = os.path.join(self.cache_dir, f"{_id}.json")
        if os.path.exists(cache_filename):
            logger.info(f'found cache at {cache_filename}, loading ...')
            cache_obj = json.load(open(cache_filename))
            logger.info('cache content')
            logger.info(json.dumps(cache_obj, ensure_ascii=False, indent=2))

        self._process_tldr(summary, cache_obj, cache_filename)
        self._process_summary(summary, cache_obj, cache_filename)
        self._process_tag_info(summary, cache_obj, cache_filename)

        ret = FormattedArxivObj(
            id=_id,
            title=arxiv_result.title,
            authors=[author.name for author in arxiv_result.authors],
            published_dt=arxiv_result.published.strftime('%Y-%m'),
            summary=summary,
            summary_cn=cache_obj['summary_cn'],
            pdf_url=arxiv_result.pdf_url,
            tldr=cache_obj['tldr'],
            raw_tldr=cache_obj['raw_tldr'],
            category=cache_obj['tag_info']['主要领域'],
            tags=cache_obj['tag_info']['标签'],
            arxiv_result=arxiv_result,
            media_type='' if hf_obj is None else hf_obj['media_type'],
            media_url='' if hf_obj is None else hf_obj['media_url']
        )
        logger.info(f'saving cache_obj to {cache_filename}')
        json.dump(cache_obj, open(cache_filename, 'w'), ensure_ascii=False, indent=2)
        return ret

    def find_by_hf_obj(self, hf_obj):
        return self.find_by_id(hf_obj['id'], hf_obj)

    def find_by_id(self, id_or_idlist, hf_obj=None, format_result=True) -> Union[FormattedArxivObj, arxiv.Result]:
        cache_filename = os.path.join(self.cache_dir, f'{id_or_idlist}.pkl')
        # if os.path.exists(cache_filename):
        #     logger.info(f"find_by_id cache hit at {cache_filename}")
        #     result = pickle.load(open(cache_filename, 'rb'))
        # else:
        #     result = next(self.client.results(arxiv.Search(id_list=id_or_idlist if isinstance(id_or_idlist, list) else [id_or_idlist])))
        result = next(self.client.results(arxiv.Search(id_list=id_or_idlist if isinstance(id_or_idlist, list) else [id_or_idlist])))
        pickle.dump(result, open(cache_filename, 'wb'))
        logger.info(f"Title: {result.title}")
        logger.info(f"Authors: {', '.join(author.name for author in result.authors)}")
        logger.info(f"Publish Date: {result.published.strftime('%Y-%m')}")
        return self._post_process(result, hf_obj) if format_result else result

    def smart_find(self, title_or_id, format_result=False):
        """
        根据标题或论文id自动查找
        :param title_or_id:
        :param format_result:
        :return:
        """
        if re.match('\d{4}.*', title_or_id) is not None:
            logger.info('using find_by_id function')
            return self.find_by_id(title_or_id, format_result=format_result)
        logger.info('using search_by_title function')
        return self.search_by_title(title_or_id, format_result=format_result)

    def search_by_title(self, title, limit=10, format_result=True) -> Union[List[FormattedArxivObj], List[arxiv.Result]]:
        data = []
        ret = {}
        search = arxiv.Search(query=f'ti:"{title}"')
        search_results = self.client.results(search)
        for result in search_results:
            logger.info(f"Title: {result.title}")
            logger.info(f"Authors: {', '.join(author.name for author in result.authors)}")
            logger.info(f"Publish Date: {result.published.strftime('%Y-%m')}")
            data.append(result)
            if len(data) >= limit:
                break
        return [self._post_process(item) for item in data] if format_result else data

    @classmethod
    def download_pdf(cls, obj: Union[FormattedArxivObj, arxiv.Result], save_dir: str):
        # 两种类都有这个属性
        title = obj.title
        filename = f"{title}.pdf"
        for ch in ('?', '/', ':', '\\'):
            filename = filename.replace(ch, '_')
        # arxiv_result.download_pdf(save_dir, filename=filename)
        path = os.path.join(save_dir, filename)
        written_path, _ = urlretrieve(obj.pdf_url, path)
        logger.info(f"{title} downloaded to {written_path}")


if __name__ == '__main__':
    print(__file__)
