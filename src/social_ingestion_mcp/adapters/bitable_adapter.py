from __future__ import annotations

import json
from uuid import uuid4

from social_ingestion_mcp.config import AppConfig
from social_ingestion_mcp.errors import ConfigError, DependencyNotAvailableError, UpstreamServiceError
from social_ingestion_mcp.models import BitableWritePayload


class FeishuBitableAdapter:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    async def upsert_record(self, payload: BitableWritePayload) -> str:
        if self._config.dry_run and not self._config.feishu_bitable_force_write:
            return f"dryrun-{payload.job_id}"

        if not all(
            [
                self._config.feishu_app_id,
                self._config.feishu_app_secret,
                self._config.feishu_bitable_app_token,
                payload.metadata.get("bitable_table_id") or self._config.feishu_bitable_table_id,
            ]
        ):
            raise ConfigError("Feishu Bitable credentials or table id are missing")

        try:
            import lark_oapi as lark  # type: ignore
            from lark_oapi.api.bitable.v1 import (  # type: ignore
                AppTableRecord,
                Condition,
                CreateAppTableRecordRequest,
                FilterInfo,
                SearchAppTableRecordRequest,
                SearchAppTableRecordRequestBody,
                UpdateAppTableRecordRequest,
            )
        except ImportError as exc:
            raise DependencyNotAvailableError("lark-oapi is not installed") from exc

        client = (
            lark.Client.builder()
            .app_id(self._config.feishu_app_id)
            .app_secret(self._config.feishu_app_secret)
            .build()
        )

        fields = self._build_fields(payload)
        table_id = self._normalize_table_id(
            payload.metadata.get("bitable_table_id") or self._config.feishu_bitable_table_id
        )
        existing_record_id = await self._find_record_id(
            client=client,
            lark=lark,
            SearchAppTableRecordRequest=SearchAppTableRecordRequest,
            SearchAppTableRecordRequestBody=SearchAppTableRecordRequestBody,
            FilterInfo=FilterInfo,
            Condition=Condition,
            table_id=str(table_id),
            job_id=payload.job_id,
        )

        request_body = AppTableRecord.builder().fields(fields).build()

        if existing_record_id:
            request = (
                UpdateAppTableRecordRequest.builder()
                .app_token(self._config.feishu_bitable_app_token)
                .table_id(str(table_id))
                .record_id(existing_record_id)
                .user_id_type(self._config.feishu_bitable_user_id_type)
                .ignore_consistency_check(True)
                .request_body(request_body)
                .build()
            )
            response = await client.bitable.v1.app_table_record.aupdate(request)
            if not response.success():
                raise UpstreamServiceError(
                    f"Feishu Bitable update failed: code={response.code}, msg={response.msg}"
                )
            record = getattr(getattr(response, "data", None), "record", None)
            return getattr(record, "record_id", existing_record_id)

        request = (
            CreateAppTableRecordRequest.builder()
            .app_token(self._config.feishu_bitable_app_token)
            .table_id(str(table_id))
            .user_id_type(self._config.feishu_bitable_user_id_type)
            .client_token(str(uuid4()))
            .ignore_consistency_check(True)
            .request_body(request_body)
            .build()
        )
        response = await client.bitable.v1.app_table_record.acreate(request)
        if not response.success():
            raise UpstreamServiceError(
                f"Feishu Bitable create failed: code={response.code}, msg={response.msg}"
            )
        record = getattr(getattr(response, "data", None), "record", None)
        record_id = getattr(record, "record_id", None)
        if not record_id:
            raise UpstreamServiceError("Feishu Bitable create succeeded without record id")
        return str(record_id)

    @staticmethod
    def _normalize_table_id(value: object) -> str:
        text = str(value or "").strip()
        if not text:
            return text
        for separator in ("?", "&"):
            if separator in text:
                text = text.split(separator, 1)[0]
        return text

    def _build_fields(self, payload: BitableWritePayload) -> dict[str, object]:
        fields: dict[str, object] = {
            self._config.feishu_bitable_job_id_field: payload.job_id,
            self._config.feishu_bitable_platform_field: payload.platform.value,
            self._config.feishu_bitable_source_url_field: payload.source_url,
            self._config.feishu_bitable_source_title_field: payload.source_title or "",
            self._config.feishu_bitable_cleaned_text_field: payload.cleaned_text,
            self._config.feishu_bitable_transcript_field: payload.transcript_text,
            self._config.feishu_bitable_status_field: "succeeded",
            self._config.feishu_bitable_media_path_field: str(payload.metadata.get("media_path") or ""),
            self._config.feishu_bitable_source_message_id_field: str(payload.metadata.get("source_message_id") or ""),
            self._config.feishu_bitable_metadata_field: json.dumps(payload.metadata, ensure_ascii=False),
        }
        for payload_key, field_name in self._config.extra_bitable_field_map().items():
            if payload_key in payload.metadata:
                fields[field_name] = payload.metadata[payload_key]
        return fields

    async def _find_record_id(
        self,
        *,
        client,
        lark,
        SearchAppTableRecordRequest,
        SearchAppTableRecordRequestBody,
        FilterInfo,
        Condition,
        table_id: str,
        job_id: str,
    ) -> str | None:
        request = (
            SearchAppTableRecordRequest.builder()
            .app_token(self._config.feishu_bitable_app_token)
            .table_id(table_id)
            .user_id_type(self._config.feishu_bitable_user_id_type)
            .page_size(1)
            .request_body(
                SearchAppTableRecordRequestBody.builder()
                .field_names([self._config.feishu_bitable_unique_field])
                .filter(
                    FilterInfo.builder()
                    .conjunction("and")
                    .conditions(
                        [
                            Condition.builder()
                            .field_name(self._config.feishu_bitable_unique_field)
                            .operator("is")
                            .value([job_id])
                            .build()
                        ]
                    )
                    .build()
                )
                .automatic_fields(False)
                .build()
            )
            .build()
        )
        response = await client.bitable.v1.app_table_record.asearch(request)
        if not response.success():
            lark.logger.warning(
                "client.bitable.v1.app_table_record.asearch failed, code: %s, msg: %s, log_id: %s",
                response.code,
                response.msg,
                response.get_log_id(),
            )
            return None
        items = getattr(getattr(response, "data", None), "items", None) or []
        if not items:
            return None
        return getattr(items[0], "record_id", None)