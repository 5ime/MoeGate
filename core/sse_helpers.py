"""SSE 流式响应辅助（容器创建 / 镜像拉取等共用）。"""
import json
import logging
from typing import Any, Iterable, Iterator, Tuple, Type

from core.exceptions import ContainerServiceError


def iter_sse_events(
    source: Iterable[Any],
    *,
    max_events: int,
    max_line_len: int,
    internal_error_msg: str,
    logger: logging.Logger,
    result_types: Tuple[Type[Any], ...] = (dict, list),
) -> Iterator[str]:
    """将服务层生成器转为 SSE 事件字符串。"""
    emitted_events = 0
    try:
        for item in source:
            if isinstance(item, result_types):
                yield f"event: result\ndata: {json.dumps(item, ensure_ascii=False)}\n\n"
                emitted_events += 1
            else:
                text = str(item)
                if len(text) > max_line_len:
                    text = f"{text[:max_line_len]}... [truncated]"
                yield f"event: log\ndata: {text}\n\n"
                emitted_events += 1

            if emitted_events >= max_events:
                yield (
                    "event: error\ndata: "
                    + json.dumps(
                        {
                            "msg": f"SSE日志事件超过上限({max_events})，已提前终止",
                            "code": 429,
                        },
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )
                break
    except ContainerServiceError as exc:
        yield f"event: error\ndata: {json.dumps({'msg': exc.message, 'code': exc.code}, ensure_ascii=False)}\n\n"
    except Exception as exc:
        logger.exception("SSE 流式操作失败: %s", exc)
        yield f"event: error\ndata: {json.dumps({'msg': internal_error_msg, 'code': 500}, ensure_ascii=False)}\n\n"
