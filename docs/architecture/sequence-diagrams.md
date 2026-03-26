# Workflow Sequence Diagrams

## Workflow A: Xiaohongshu Silent Scraping Pipeline

```mermaid
sequenceDiagram
    autonumber
    participant User as User in Feishu
    participant Bot as OpenClaw Bot
    participant Skill as OpenClaw Skill
    participant MCP as social-ingestion-mcp
    participant XHS as XHS Adapter
    participant Media as Media Pipeline
    participant STT as STT Engine
    participant Clean as LLM Cleaner
    participant Bitable as Feishu Bitable API

    User->>Bot: Send Xiaohongshu post link
    Bot->>Skill: Intent parse and link extraction
    Skill->>MCP: submit_xhs_ingestion(source_url, source_message_id)
    MCP-->>Skill: job_id, queued/running
    Skill-->>Bot: Task accepted with job_id
    Bot-->>User: Processing started

    MCP->>XHS: Extract note metadata and media URLs
    XHS-->>MCP: title, raw_text, optional video
    alt Video exists
        MCP->>Media: Extract audio from mp4 with ffmpeg
        Media-->>MCP: wav path
        MCP->>STT: Transcribe wav
        STT-->>MCP: transcript_text
    else Text only
        MCP->>MCP: Use note text as primary text source
    end
    MCP->>Clean: Normalize and clean transcript plus note text
    Clean-->>MCP: cleaned_text
    MCP->>Bitable: Upsert structured record
    Bitable-->>MCP: record_id

    loop Poll every 5s
        Skill->>MCP: get_ingestion_job(job_id)
        MCP-->>Skill: state, stage, result_preview
    end

    Skill-->>Bot: Final compact result
    Bot-->>User: Success or failure summary
```

## Workflow B: WeChat Channels RPA Pipeline

```mermaid
sequenceDiagram
    autonumber
    participant User as User in Feishu
    participant Bot as OpenClaw Bot
    participant Skill as OpenClaw Skill
    participant MCP as social-ingestion-mcp
    participant Queue as Single-Flight RPA Queue
    participant Node as Local RPA Node
    participant WeChat as WeChat PC
    participant Sniffer as Background Sniffer
    participant Decrypt as WechatSphDecrypt
    participant Media as Media Pipeline
    participant STT as STT Engine
    participant Clean as LLM Cleaner
    participant Bitable as Feishu Bitable API

    User->>Bot: Send WeChat Channels link
    Bot->>Skill: Intent parse and link extraction
    Skill->>MCP: submit_wechat_channels_ingestion(source_url, source_message_id, desktop_node_id)
    MCP->>Queue: Enqueue job in single-thread lane
    Queue-->>MCP: queue_position
    MCP-->>Skill: job_id, queue_position
    Skill-->>Bot: Task accepted
    Bot-->>User: Queued for desktop processing

    Queue->>Node: Dispatch next task
    Node->>WeChat: Focus window, paste link, send message
    Node->>WeChat: Click play and keep window active
    par Capture stream
        Node->>Sniffer: Start intercept
        Sniffer-->>Node: .sph or encrypted video chunks
        Node->>Decrypt: Decrypt sph to mp4
        Decrypt-->>Node: mp4 path
    and Gather metadata
        Node->>WeChat: Read visible title or caption if available
    end
    Node-->>MCP: task succeeded with mp4 path and metadata
    MCP->>Media: Extract audio with ffmpeg
    Media-->>MCP: wav path
    MCP->>STT: Transcribe wav
    STT-->>MCP: transcript_text
    MCP->>Clean: Clean transcript
    Clean-->>MCP: cleaned_text
    MCP->>Bitable: Upsert structured record
    Bitable-->>MCP: record_id

    loop Poll every 5s
        Skill->>MCP: get_ingestion_job(job_id)
        MCP-->>Skill: state, stage, queue_position, result_preview
    end

    Skill-->>Bot: Final compact result
    Bot-->>User: Success or failure summary
```

## Design Notes

- OpenClaw only submits and polls by job id.
- WeChat Channels always runs through a single-thread queue.
- Long transcript and cleaned正文 stay inside MCP and storage layers, not agent context.