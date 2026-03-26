from __future__ import annotations

import json

import lark_oapi as lark
from lark_oapi.api.bitable.v1 import ListAppTableFieldRequest

from social_ingestion_mcp.adapters.bitable_adapter import FeishuBitableAdapter
from social_ingestion_mcp.config import AppConfig


def main() -> int:
    config = AppConfig()
    table_id = FeishuBitableAdapter._normalize_table_id(config.feishu_bitable_table_id)
    client = (
        lark.Client.builder()
        .app_id(config.feishu_app_id)
        .app_secret(config.feishu_app_secret)
        .build()
    )
    request = (
        ListAppTableFieldRequest.builder()
        .app_token(config.feishu_bitable_app_token)
        .table_id(table_id)
        .page_size(500)
        .build()
    )
    response = client.bitable.v1.app_table_field.list(request)
    if not response.success():
        print(
            json.dumps(
                {
                    "ok": False,
                    "code": response.code,
                    "msg": response.msg,
                    "log_id": response.get_log_id(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    items = getattr(getattr(response, "data", None), "items", None) or []
    actual_fields = {str(getattr(item, "field_name", "")).strip(): item for item in items}
    expected = {
        "unique_field": config.feishu_bitable_unique_field,
        "job_id_field": config.feishu_bitable_job_id_field,
        "platform_field": config.feishu_bitable_platform_field,
        "source_url_field": config.feishu_bitable_source_url_field,
        "source_title_field": config.feishu_bitable_source_title_field,
        "cleaned_text_field": config.feishu_bitable_cleaned_text_field,
        "transcript_field": config.feishu_bitable_transcript_field,
        "status_field": config.feishu_bitable_status_field,
        "media_path_field": config.feishu_bitable_media_path_field,
        "source_message_id_field": config.feishu_bitable_source_message_id_field,
        "metadata_field": config.feishu_bitable_metadata_field,
    }
    missing = {key: value for key, value in expected.items() if value not in actual_fields}
    payload = {
        "ok": not missing,
        "table_id": table_id,
        "expected": expected,
        "missing": missing,
        "actual_fields": [
            {
                "field_id": getattr(item, "field_id", None),
                "field_name": getattr(item, "field_name", None),
                "type": getattr(item, "type", None),
                "ui_type": getattr(item, "ui_type", None),
                "is_primary": getattr(item, "is_primary", None),
            }
            for item in items
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())