"""
 Created by luogang on 2024/2/29
"""
import os
import requests

from entity.formatted_arxiv_obj import FormattedArxivObj
import common_utils

logger = common_utils.get_logger(__name__)


class NotionService:
    def __init__(self, create_time, db_id=os.environ['NOTION_DB_ID'], secret=os.environ['NOTION_SECRET']):
        self.db_id = db_id
        self.secret = secret
        self.create_time = create_time

        self._req_body = {}
        self._properties = {}
        self._blocks = []

    def set_database_id(self, db_id):
        self._req_body['parent'] = {
            'database_id': db_id
        }
        return self

    def add_property_title(self, column, content):
        self._properties[column] = {
            "title": [
                {
                    "text": {
                        "content": content
                    }
                }
            ]
        }
        return self

    def add_property_rich_text(self, column, content):
        self._properties[column] = {
            "rich_text": [
                {
                    "text": {
                        "content": content
                    }
                }
            ]
        }
        return self

    def add_property_date(self, column, content):
        self._properties[column] = {
            "date": {
                "start": content
            }
        }
        return self

    def add_property_select(self, column, content):
        self._properties[column] = {
            "select": {
                "name": content
            }
        }
        return self

    def add_property_multi_select(self, column, arr):
        self._properties[column] = {
            "multi_select": [{"name": tag} for tag in arr]
        }
        return self

    def add_property_url(self, column, content):
        self._properties[column] = {
            "url": content
        }
        return self

    def _add_block(self, block_type, content):
        self._blocks.append({
            "object": "block",
            "type": block_type,
            block_type: {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": content
                        }
                    }
                ]
            }
        })

    def _add_media_block(self, media_type, url):
        self._blocks.append({
            "object": "block",
            "type": media_type,
            media_type: {
                "type": "external",
                "external": {
                    "url": url
                }
            }
        })
        return self

    def add_h1(self, content):
        self._add_block("heading_1", content)
        return self

    def add_h2(self, content):
        self._add_block("heading_2", content)
        return self

    def add_h3(self, content):
        self._add_block("heading_3", content)
        return self

    def add_paragraph(self, content):
        self._add_block("paragraph", content)
        return self

    def add_image(self, url):
        self._add_media_block('image', url)
        return self

    def add_video(self, url):
        self._add_media_block('video', url)
        return self

    def _send(self):
        headers = {
            'Authorization': f'Bearer {self.secret}',
            'Notion-Version': '2022-06-28',
            'Content-Type': 'application/json'
        }
        self._req_body['properties'] = self._properties
        self._req_body['children'] = self._blocks
        resp = requests.post(
            'https://api.notion.com/v1/pages', headers=headers, json=self._req_body
        )
        if resp.status_code != 200:
            logger.warning(f"status_code not 200, response:")
            logger.warning(resp.json())

        logger.debug("send response")
        logger.debug(resp.json())
        self._req_body = {}
        self._properties = {}
        self._blocks = []

    def insert(self, hf_obj, formatted_arxiv_obj: FormattedArxivObj):
        self.set_database_id(
            self.db_id
        ).add_property_title(
            '标题', formatted_arxiv_obj.title
        ).add_property_date(
            '日期', self.create_time.strftime('%Y-%m-%d')
        ).add_property_rich_text(
            '首次发表日期', formatted_arxiv_obj.published_dt
        ).add_property_rich_text(
            '作者', ', '.join(formatted_arxiv_obj.authors)
        ).add_property_select(
            '领域', formatted_arxiv_obj.category
        ).add_property_url(
            'PDF链接', formatted_arxiv_obj.pdf_url
        ).add_property_multi_select(
            'Tags', formatted_arxiv_obj.tags
        )._add_media_block(
            hf_obj['media_type'], hf_obj['media_url']
        )
        tldr_keys = ('动机', '方法', '结果')
        self.add_h1(
            'TL;DR'
        )
        if any([key in formatted_arxiv_obj.tldr and formatted_arxiv_obj.tldr[key] != '' for key in tldr_keys]):
            for key in tldr_keys:
                if key in formatted_arxiv_obj.tldr and formatted_arxiv_obj.tldr[key] != '':
                    self.add_h2(
                        key
                    ).add_paragraph(
                        formatted_arxiv_obj.tldr[key]
                    )
        else:
            self.add_paragraph(formatted_arxiv_obj.raw_tldr)

        self.add_h1(
            '摘要'
        ).add_h2(
            '原文'
        ).add_paragraph(
            formatted_arxiv_obj.summary
        ).add_h2(
            '中文译文'
        ).add_paragraph(
            formatted_arxiv_obj.summary_cn
        )
        self._send()
