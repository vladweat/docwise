"""Cookie session after password, Google, SSO, refresh, or switch-org."""

from fastapi import Response

from app.core.auth_cookies import create_refresh_token, set_auth_cookies
from app.core.principal import Principal
from app.core.security import create_access_token
from app.services.org.sso import mark_sso_fresh


def issue_session(principal: Principal, response: Response, *, sso: bool = False) -> Principal:
    """Set host-only `dw_*` cookies for the resolved Principal org."""
    org_id = str(principal.organization_id)
    access = create_access_token(principal.email, org_id=org_id, sso=sso)
    refresh = create_refresh_token(principal.email, org_id=org_id, sso=sso)
    set_auth_cookies(response, access_token=access, refresh_token=refresh)
    if sso:
        mark_sso_fresh(principal.id, principal.organization_id)
    return principal
