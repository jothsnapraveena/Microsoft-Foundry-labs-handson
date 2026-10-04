"""FastAPI tool service. Each agent tool is one operation; /confirmations is for the customer client only."""
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

from .auth import CUSTOMER_CHANNEL, AuthError, Identity, build_authenticator
from .config import Clock, Settings
from .eligibility import ReturnRequest
from .policies import PolicyStore
from .repository import SqliteRepository
from .service import Conflict, InvalidConfirmation, NotFound, SupportService


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EligibilityBody(Body):
    order_id: str = Field(max_length=40)
    item_id: str = Field(max_length=60)
    quantity: StrictInt
    reason: str = Field(max_length=40)
    condition: str = Field(max_length=40)
    accessories_present: StrictBool
    original_packaging: StrictBool


class ConfirmedWriteBody(Body):
    proposal_id: str = Field(max_length=60)
    confirmation_token: str = Field(max_length=200)


class OrderBody(Body):
    order_id: str = Field(max_length=40)


class TicketBody(Body):
    category: str = Field(max_length=40)
    summary: str = Field(max_length=1000)
    order_id: str | None = Field(default=None, max_length=40)


class ConfirmationBody(Body):
    proposal_id: str = Field(max_length=60)


def trace_id_from(traceparent):
    """The trace id from a W3C traceparent header, so audit rows link to traces."""
    parts = (traceparent or "").split("-")
    return parts[1] if len(parts) == 4 and len(parts[1]) == 32 else None


def create_app(settings=None, service=None, authenticator=None):
    settings = settings or Settings.from_env()
    if service is None:
        if not settings.db_path.exists():
            raise RuntimeError(f"{settings.db_path} not found. Run: python -m northstar.setup_db")
        repository = SqliteRepository(settings.db_path)
        service = SupportService(repository, PolicyStore.load(settings.dataset_dir / "knowledge" / "policies.json"),
                                 Clock(settings.fixed_date), settings.proposal_ttl_seconds, settings.region)
    authenticator = authenticator or build_authenticator(settings, service.repository)
    app = FastAPI(title="Northstar support tools", version="0.1.0")

    def identity(request: Request) -> Identity:
        try:
            return authenticator.authenticate(request.headers)
        except AuthError:
            raise HTTPException(401, "Not authenticated")

    def trace(traceparent: str | None = Header(default=None)):
        return trace_id_from(traceparent)

    for error, status in ((NotFound, 404), (Conflict, 409), (InvalidConfirmation, 403), (ValueError, 422)):
        app.add_exception_handler(error, lambda request, exc, status=status: JSONResponse({"detail": str(exc)}, status))

    @app.get("/health", include_in_schema=False)
    def health():
        return {"status": "ok", "auth_mode": settings.auth_mode, "business_date": str(service.clock.today())}

    @app.get("/orders/{order_id}", operation_id="get_order")
    def get_order(order_id: str, who: Identity = Depends(identity), trace_id=Depends(trace)):
        """Look up one of the signed-in customer's orders, with its items and shipment."""
        return service.get_order(who.customer_id, order_id, trace_id)

    @app.post("/returns/eligibility", operation_id="check_return_eligibility")
    def check_return_eligibility(body: EligibilityBody, who: Identity = Depends(identity), trace_id=Depends(trace)):
        """Decide whether a return is eligible. Read-only; an eligible result includes a proposal to confirm."""
        return service.check_return_eligibility(who.customer_id, ReturnRequest(**body.model_dump()), trace_id)

    @app.post("/returns", operation_id="create_return")
    def create_return(body: ConfirmedWriteBody, idempotency_key: str = Header(), who: Identity = Depends(identity), trace_id=Depends(trace)):
        """Create a return authorization from a proposal the customer has confirmed. Does not issue a refund."""
        return service.create_return(who.customer_id, body.proposal_id, body.confirmation_token, idempotency_key, trace_id)

    @app.get("/returns/{return_id}", operation_id="get_return_status")
    def get_return_status(return_id: str, who: Identity = Depends(identity), trace_id=Depends(trace)):
        """Status of one of the customer's returns, with its refund record when one exists."""
        return service.get_return_status(who.customer_id, return_id, trace_id)

    @app.post("/cancellations/proposal", operation_id="propose_cancel_order")
    def propose_cancel_order(body: OrderBody, who: Identity = Depends(identity), trace_id=Depends(trace)):
        """Check whether an order can be cancelled. Read-only; returns a proposal to confirm when it can."""
        return service.propose_cancel_order(who.customer_id, body.order_id, trace_id)

    @app.post("/cancellations", operation_id="cancel_order")
    def cancel_order(body: ConfirmedWriteBody, idempotency_key: str = Header(), who: Identity = Depends(identity), trace_id=Depends(trace)):
        """Cancel a processing order from a proposal the customer has confirmed."""
        return service.cancel_order(who.customer_id, body.proposal_id, body.confirmation_token, idempotency_key, trace_id)

    @app.post("/tickets/proposal", operation_id="propose_support_ticket")
    def propose_support_ticket(body: TicketBody, who: Identity = Depends(identity), trace_id=Depends(trace)):
        """Prepare a support ticket for review cases. Read-only; returns a proposal to confirm."""
        return service.propose_support_ticket(who.customer_id, body.category, body.summary, body.order_id, trace_id)

    @app.post("/tickets", operation_id="create_support_ticket")
    def create_support_ticket(body: ConfirmedWriteBody, idempotency_key: str = Header(), who: Identity = Depends(identity), trace_id=Depends(trace)):
        """Create a support ticket from a proposal the customer has confirmed."""
        return service.create_support_ticket(who.customer_id, body.proposal_id, body.confirmation_token, idempotency_key, trace_id)

    # Hidden from the OpenAPI document so it is never registered as an agent tool.
    @app.post("/confirmations", include_in_schema=False)
    def confirm(body: ConfirmationBody, who: Identity = Depends(identity), trace_id=Depends(trace)):
        if who.channel != CUSTOMER_CHANNEL:
            raise HTTPException(403, "Confirmation must come from the customer")
        return service.confirm(who.customer_id, body.proposal_id, trace_id)

    return app
