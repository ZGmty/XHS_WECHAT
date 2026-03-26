from __future__ import annotations

import argparse
import json
import time
from collections.abc import Iterable
from uuid import uuid4

import lark_oapi as lark
from lark_oapi.api.bitable.v1 import AppTableField, CreateAppTableFieldRequest, ListAppTableFieldRequest

from social_ingestion_mcp.adapters.bitable_adapter import FeishuBitableAdapter
from social_ingestion_mcp.config import AppConfig


def expected_field_names(config: AppConfig) -> list[str]:
    ordered = [
        config.feishu_bitable_unique_field,
        config.feishu_bitable_job_id_field,
        config.feishu_bitable_platform_field,
        config.feishu_bitable_source_url_field,
        config.feishu_bitable_source_title_field,
        config.feishu_bitable_cleaned_text_field,
        config.feishu_bitable_transcript_field,
        config.feishu_bitable_status_field,
        config.feishu_bitable_media_path_field,
        config.feishu_bitable_source_message_id_field,
        config.feishu_bitable_metadata_field,
    ]
    deduplicated: list[str] = []
    seen: set[str] = set()
    for value in ordered:
        name = str(value).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        deduplicated.append(name)
    return deduplicated


def fetch_existing_fields(client: lark.Client, config: AppConfig, table_id: str) -> list[object]:
    request = (
        ListAppTableFieldRequest.builder()
        .app_token(config.feishu_bitable_app_token)
        .table_id(table_id)
        .page_size(500)
        .build()
    )
    response = client.bitable.v1.app_table_field.list(request)
    if not response.success():
        raise RuntimeError(
            f"List fields failed: code={response.code}, msg={response.msg}, log_id={response.get_log_id()}"
        )
    return list(getattr(getattr(response, "data", None), "items", None) or [])


def summarize_fields(items: Iterable[object]) -> list[dict[str, object]]:
    return [
        {
            "field_id": getattr(item, "field_id", None),
            "field_name": getattr(item, "field_name", None),
            "type": getattr(item, "type", None),
            "ui_type": getattr(item, "ui_type", None),
            "is_primary": getattr(item, "is_primary", None),
        }
        for item in items
    ]


def create_text_field(client: lark.Client, config: AppConfig, table_id: str, field_name: str) -> dict[str, object]:
    request = (
        CreateAppTableFieldRequest.builder()
        .app_token(config.feishu_bitable_app_token)
        .table_id(table_id)
        .client_token(str(uuid4()))
        .request_body(
            AppTableField.builder()
            .field_name(field_name)
            .type(1)
            .ui_type("Text")
            .build()
        )
        .build()
    )
    response = client.bitable.v1.app_table_field.create(request)
    if not response.success():
        raise RuntimeError(
            f"Create field '{field_name}' failed: code={response.code}, msg={response.msg}, log_id={response.get_log_id()}"
        )
    field = getattr(getattr(response, "data", None), "field", None)
    return {
        "field_id": getattr(field, "field_id", None),
        "field_name": getattr(field, "field_name", field_name),
        "type": getattr(field, "type", None),
        "ui_type": getattr(field, "ui_type", None),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview or create missing Feishu Bitable text fields")
    parser.add_argument("--apply", action="store_true", help="Create missing fields instead of previewing only")
    args = parser.parse_args()

    config = AppConfig()
    table_id = FeishuBitableAdapter._normalize_table_id(config.feishu_bitable_table_id)
    client = (
        lark.Client.builder()
        .app_id(config.feishu_app_id)
        .app_secret(config.feishu_app_secret)
        .build()
    )

    existing_items = fetch_existing_fields(client, config, table_id)
    existing_names = {str(getattr(item, "field_name", "")).strip() for item in existing_items}
    planned = expected_field_names(config)
    missing = [name for name in planned if name not in existing_names]

    payload: dict[str, object] = {
        "ok": not missing,
        "apply": args.apply,
        "table_id": table_id,
        "planned_fields": planned,
        "missing_fields": missing,
        "existing_fields": summarize_fields(existing_items),
    }

    if not args.apply:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if not missing else 2

    created: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    for field_name in missing:
        try:
            created.append(create_text_field(client, config, table_id, field_name))
            time.sleep(0.5)
        except Exception as exc:
            failures.append({"field_name": field_name, "error": str(exc)})

    refreshed = fetch_existing_fields(client, config, table_id)
    refreshed_names = {str(getattr(item, "field_name", "")).strip() for item in refreshed}
    still_missing = [name for name in planned if name not in refreshed_names]
    payload.update(
        {
            "ok": not still_missing and not failures,
            "created_fields": created,
            "failures": failures,
            "still_missing": still_missing,
            "existing_fields": summarize_fields(refreshed),
        }
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not still_missing and not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())