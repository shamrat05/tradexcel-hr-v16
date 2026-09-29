import pytest

from tradex_hr.tradexcel_hr.company_context import resolve_company


def test_explicit_company_is_required_when_no_user_default(monkeypatch):
    monkeypatch.setattr("tradex_hr.tradexcel_hr.company_context.user_default_company", lambda: None)
    with pytest.raises(ValueError, match="Company is required"):
        resolve_company({})


def test_user_default_company_is_used_when_filter_is_blank(monkeypatch):
    monkeypatch.setattr(
        "tradex_hr.tradexcel_hr.company_context.user_default_company",
        lambda: "Elegance Footwear Ltd.",
    )
    assert resolve_company({}) == "Elegance Footwear Ltd."


def test_explicit_company_wins_over_user_default(monkeypatch):
    monkeypatch.setattr(
        "tradex_hr.tradexcel_hr.company_context.user_default_company",
        lambda: "Elegance Footwear Ltd.",
    )
    assert resolve_company({"company": "Tradexcel Ceramics Ltd."}) == "Tradexcel Ceramics Ltd."


def test_payroll_manager_without_company_permission_is_denied(monkeypatch):
    from types import SimpleNamespace

    from tradex_hr.tradexcel_hr import company_context

    class PermissionError(Exception):
        pass

    fake_frappe = SimpleNamespace(
        db=SimpleNamespace(exists=lambda doctype, filters=None: doctype == "Company"),
        session=SimpleNamespace(user="payroll@example.com"),
        get_roles=lambda user=None: ["Tradexcel Payroll Manager"],
        has_permission=lambda *args, **kwargs: True,
        PermissionError=PermissionError,
        throw=lambda message, exception, *args, **kwargs: (_ for _ in ()).throw(exception(message)),
    )
    monkeypatch.setattr(company_context, "frappe", fake_frappe)

    with pytest.raises(PermissionError, match="explicit Company User Permission"):
        company_context.assert_company_access(
            "Tradexcel Ceramics Ltd.", require_explicit_scope=True
        )


def test_attendance_officer_denied_by_default_under_explicit_scope(monkeypatch):
    from types import SimpleNamespace
    from tradex_hr.tradexcel_hr import company_context

    class PermissionError(Exception):
        pass

    fake_frappe = SimpleNamespace(
        db=SimpleNamespace(exists=lambda doctype, filters=None: True),
        session=SimpleNamespace(user="attendance@example.com"),
        get_roles=lambda user=None: ["Tradexcel HR/Attendance Officer"],
        has_permission=lambda *args, **kwargs: True,
        PermissionError=PermissionError,
        throw=lambda message, exception, *args, **kwargs: (_ for _ in ()).throw(exception(message)),
    )
    monkeypatch.setattr(company_context, "frappe", fake_frappe)

    # By default, Attendance Officer is not in DEFAULT_EXPLICIT_SCOPE_ROLES
    with pytest.raises(PermissionError, match="explicit Company User Permission"):
        company_context.assert_company_access(
            "Tradexcel Ceramics Ltd.", require_explicit_scope=True
        )


def test_attendance_officer_allowed_when_additional_roles_opted_in(monkeypatch):
    from types import SimpleNamespace
    from tradex_hr.tradexcel_hr import company_context

    class PermissionError(Exception):
        pass

    fake_frappe = SimpleNamespace(
        db=SimpleNamespace(exists=lambda doctype, filters=None: True),
        session=SimpleNamespace(user="attendance@example.com"),
        get_roles=lambda user=None: ["Tradexcel HR/Attendance Officer"],
        has_permission=lambda *args, **kwargs: True,
        PermissionError=PermissionError,
        throw=lambda message, exception, *args, **kwargs: (_ for _ in ()).throw(exception(message)),
    )
    monkeypatch.setattr(company_context, "frappe", fake_frappe)

    # When opted in via additional_explicit_roles and user permission exists
    result = company_context.assert_company_access(
        "Tradexcel Ceramics Ltd.",
        require_explicit_scope=True,
        additional_explicit_roles={"Tradexcel HR/Attendance Officer"},
    )
    assert result == "Tradexcel Ceramics Ltd."


def test_attendance_officer_denied_with_opt_in_if_company_permission_missing(monkeypatch):
    from types import SimpleNamespace
    from tradex_hr.tradexcel_hr import company_context

    class PermissionError(Exception):
        pass

    # Exists for Company, but User Permission does not exist
    def fake_exists(doctype, filters=None):
        if doctype == "Company":
            return True
        if doctype == "User Permission":
            return False
        return False

    fake_frappe = SimpleNamespace(
        db=SimpleNamespace(exists=fake_exists),
        session=SimpleNamespace(user="attendance@example.com"),
        get_roles=lambda user=None: ["Tradexcel HR/Attendance Officer"],
        has_permission=lambda *args, **kwargs: True,
        PermissionError=PermissionError,
        throw=lambda message, exception, *args, **kwargs: (_ for _ in ()).throw(exception(message)),
    )
    monkeypatch.setattr(company_context, "frappe", fake_frappe)

    with pytest.raises(PermissionError, match="explicit Company User Permission"):
        company_context.assert_company_access(
            "Tradexcel Ceramics Ltd.",
            require_explicit_scope=True,
            additional_explicit_roles={"Tradexcel HR/Attendance Officer"},
        )
