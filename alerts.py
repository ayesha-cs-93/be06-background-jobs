"""
Alert stub — for this assignment, logging is enough to satisfy
"someone must find out" when a job fails permanently.
In production, replace the body with a Slack webhook, email (e.g. via SES),
or a paging service call.
"""
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("alerts")


def send_alert(message: str) -> None:
    logger.error(f"[ALERT] {message}")
    # TODO (production): POST to Slack webhook or send email here.
