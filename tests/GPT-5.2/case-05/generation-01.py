```python
import pytest
from datetime import datetime, timedelta


# NOTE:
# These tests assume the SUT provides the following importable classes with the
# specified methods/attributes from the formal specification:
# - ReservationService
# - Reservation (returned by createReservation)
# - Flight (internally stored/used by the service)
#
# Adjust the import path below to match your project structure.
from reservation_system import ReservationService  # noqa: F401


# -----------------------------
# Helper fixtures / utilities
# -----------------------------

@pytest.fixture
def service():
    # Deterministic setup; no external time sources are used by tests.
    return ReservationService()


def _freeze_datetime(value: datetime):
    """
    Returns a minimal object compatible with monkeypatching a module's `datetime`
    reference (if the SUT uses `datetime.now()` via an imported `datetime` name).

    This does NOT enforce that the SUT uses system time; tests that validate BR15
    explicitly check behavior independence from any patched 'now'.
    """
    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return value if tz is None else value.astimezone(tz)

    return _FrozenDateTime


# -----------------------------
# BR01 – exactly one approved payment is required to confirm reservation
# -----------------------------

def test_br01_confirm_reservation_only_with_exactly_one_approved_payment(service):
    # BR01 – A reservation may only be confirmed if exactly one approved payment is associated with it
    r = service.createReservation(flightId="F1", seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)
    assert r.state == "CONFIRMED"


def test_br01_confirm_reservation_rejected_when_no_payment_approved(service):
    # BR01 – A reservation may only be confirmed if exactly one approved payment is associated with it
    r = service.createReservation(flightId="F1", seat=1)
    with pytest.raises(Exception):
        # Attempt to confirm reservation without approving the payment is not an operation provided;
        # thus, the only way to attempt confirmation is via confirmPayment(False) which must not confirm.
        service.confirmPayment(reservationId=r.id, paymentApproved=False)
    assert r.state == "CREATED"


# -----------------------------
# BR02 – non-approved payments must not confirm reservations
# -----------------------------

def test_br02_non_approved_payment_must_not_confirm_reservation(service):
    # BR02 – Payments with a status other than approved must not confirm reservations
    r = service.createReservation(flightId="F1", seat=1)
    with pytest.raises(Exception):
        service.confirmPayment(reservationId=r.id, paymentApproved=False)
    assert r.state == "CREATED"


# -----------------------------
# BR03 – confirmation and payment approval must be atomic
# -----------------------------

def test_br03_payment_approval_and_reservation_confirmation_are_atomic_on_success(service):
    # BR03 – Reservation confirmation and payment approval must occur atomically
    r = service.createReservation(flightId="F1", seat=1)

    # Operation completes successfully -> reservation must be CONFIRMED immediately.
    service.confirmPayment(reservationId=r.id, paymentApproved=True)
    assert r.state == "CONFIRMED"


def test_br03_no_partial_state_change_on_failed_confirm_payment(service):
    # BR03 – No observable state may exist in which only one of the two has been completed
    r = service.createReservation(flightId="F1", seat=1)

    with pytest.raises(Exception):
        service.confirmPayment(reservationId=r.id, paymentApproved=False)

    # If operation fails, reservation must remain CREATED (no partial confirmation).
    assert r.state == "CREATED"


# -----------------------------
# BR04 – seat exclusivity per active reservation per flight
# -----------------------------

def test_br04_same_seat_cannot_be_allocated_to_two_active_reservations_same_flight(service):
    # BR04 – A seat may belong to at most one active reservation per flight
    r1 = service.createReservation(flightId="F1", seat=1)
    assert r1.seat == 1
    with pytest.raises(Exception):
        service.createReservation(flightId="F1", seat=1)


# -----------------------------
# BR05 – canceled reservations must immediately release seat
# -----------------------------

def test_br05_cancel_releases_seat_immediately(service):
    # BR05 – Canceled reservations must immediately release the associated seat
    r1 = service.createReservation(flightId="F1", seat=1)
    service.confirmPayment(reservationId=r1.id, paymentApproved=True)
    service.cancelReservation(reservationId=r1.id)
    assert r1.state == "CANCELED"

    # Seat must be available for a new reservation immediately after cancellation.
    r2 = service.createReservation(flightId="F1", seat=1)
    assert r2.seat == 1
    assert r2.state == "CREATED"


# -----------------------------
# BR06 – overbooking not permitted under any circumstances
# -----------------------------

def test_br06_overbooking_not_permitted_when_all_seats_taken(service):
    # BR06 – Overbooking is not permitted under any circumstances
    # Assumes the flight has a deterministic, fixed total seat count available in the system.
    # This test uses seat uniqueness as the direct mechanism to avoid overbooking.
    r1 = service.createReservation(flightId="F_OVERBOOK", seat=1)
    r2 = service.createReservation(flightId="F_OVERBOOK", seat=2)
    r3 = service.createReservation(flightId="F_OVERBOOK", seat=3)

    # Attempt to create another reservation on an already allocated seat must fail (no overbooking).
    with pytest.raises(Exception):
        service.createReservation(flightId="F_OVERBOOK", seat=1)

    # Ensure existing reservations remain unchanged after failure.
    assert r1.state == "CREATED"
    assert r2.state == "CREATED"
    assert r3.state == "CREATED"


# -----------------------------
# BR07 – confirmed reservations count must not exceed total available seats
# -----------------------------

def test_br07_confirmed_reservations_must_not_exceed_total_seats(service):
    # BR07 – The number of confirmed reservations for a flight must never exceed total seats
    # This is validated by confirming distinct seats, and rejecting any seat reuse for the same flight.
    r1 = service.createReservation(flightId="F1", seat=1)
    r2 = service.createReservation(flightId="F1", seat=2)

    service.confirmPayment(reservationId=r1.id, paymentApproved=True)
    service.confirmPayment(reservationId=r2.id, paymentApproved=True)

    # Any attempt to confirm an additional reservation for a seat already taken must fail upstream at creation.
    with pytest.raises(Exception):
        service.createReservation(flightId="F1", seat=1)


# -----------------------------
# BR08 – reservation must be exclusively in CREATED/CONFIRMED/CANCELED
# -----------------------------

def test_br08_reservation_initial_state_is_created(service):
    # BR08 – Reservation may be exclusively in CREATED/CONFIRMED/CANCELED
    r = service.createReservation(flightId="F1", seat=1)
    assert r.state == "CREATED"


# -----------------------------
# BR09 – intermediate/additional states not permitted
# -----------------------------

def test_br09_no_intermediate_state_exposed_during_confirm_payment(service):
    # BR09 – Intermediate or additional states are not permitted
    r = service.createReservation(flightId="F1", seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)
    assert r.state in ("CREATED", "CONFIRMED", "CANCELED")
    assert r.state == "CONFIRMED"


# -----------------------------
# BR10 – only valid transitions: CREATED→CONFIRMED, CONFIRMED→CANCELED
# -----------------------------

def test_br10_valid_transition_created_to_confirmed(service):
    # BR10 – Valid transition: CREATED → CONFIRMED
    r = service.createReservation(flightId="F1", seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)
    assert r.state == "CONFIRMED"


def test_br10_valid_transition_confirmed_to_canceled(service):
    # BR10 – Valid transition: CONFIRMED → CANCELED
    r = service.createReservation(flightId="F1", seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)
    service.cancelReservation(reservationId=r.id)
    assert r.state == "CANCELED"


# -----------------------------
# BR11 – any other state transition must be rejected
# -----------------------------

def test_br11_reject_transition_created_to_canceled(service):
    # BR11 – Any state transition other than those defined must be rejected
    r = service.createReservation(flightId="F1", seat=1)
    with pytest.raises(Exception):
        service.cancelReservation(reservationId=r.id)
    assert r.state == "CREATED"


def test_br11_reject_transition_confirmed_to_confirmed(service):
    # BR11 – Any state transition other than those defined must be rejected
    r = service.createReservation(flightId="F1", seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)
    with pytest.raises(Exception):
        # A second confirmPayment would imply CONFIRMED -> CONFIRMED (invalid)
        service.confirmPayment(reservationId=r.id, paymentApproved=True)
    assert r.state == "CONFIRMED"


# -----------------------------
# BR12 – canceled reservation must not be reactivated, modified, or receive new payments
# -----------------------------

def test_br12_canceled_reservation_cannot_receive_new_payment(service):
    # BR12 – A canceled reservation must not be reactivated, modified, or receive new payments
    r = service.createReservation(flightId="F1", seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)
    service.cancelReservation(reservationId=r.id)

    with pytest.raises(Exception):
        service.confirmPayment(reservationId=r.id, paymentApproved=True)
    assert r.state == "CANCELED"


def test_br12_canceled_reservation_cannot_be_reactivated(service):
    # BR12 – A canceled reservation must not be reactivated
    r = service.createReservation(flightId="F1", seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)
    service.cancelReservation(reservationId=r.id)

    with pytest.raises(Exception):
        # Any attempt to move to CONFIRMED again is invalid; only operation available is confirmPayment.
        service.confirmPayment(reservationId=r.id, paymentApproved=True)
    assert r.state == "CANCELED"


# -----------------------------
# BR13 – refund policy based on remaining time threshold (>=24h full refund, <24h no refund)
# -----------------------------

def test_br13_cancel_with_remaining_time_ge_24_hours_results_in_full_refund(service, monkeypatch):
    # BR13 – Remaining time ≥ 24 hours before the flight → full refund
    # This test expects the cancel operation to expose a deterministic refund record/result.
    # If SUT stores refund as a property or emits a record, it must be accessible deterministically.
    #
    # The specification requires the policy; it does not define a return type.
    # Therefore, this test asserts a minimal observable: an immutable operation record with refund outcome.
    now = datetime(2026, 1, 12, 0, 0, 0)
    monkeypatch.setattr("reservation_system.datetime", _freeze_datetime(now), raising=False)

    r = service.createReservation(flightId="F_REFUND_24H", seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)

    # Set flight datetime internally via the service API is not specified; thus this test assumes
    # the system already has an internally stored flight dateTime for flightId.
    result = service.cancelReservation(reservationId=r.id)

    assert getattr(result, "refund", None) == "FULL"


def test_br13_cancel_with_remaining_time_lt_24_hours_results_in_no_refund(service, monkeypatch):
    # BR13 – Remaining time < 24 hours before the flight → no refund
    now = datetime(2026, 1, 12, 0, 0, 0)
    monkeypatch.setattr("reservation_system.datetime", _freeze_datetime(now), raising=False)

    r = service.createReservation(flightId="F_REFUND_23H", seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)

    result = service.cancelReservation(reservationId=r.id)

    assert getattr(result, "refund", None) == "NONE"


# -----------------------------
# BR14 – remaining time calculated in exact hours, no rounding/tolerance
# -----------------------------

def test_br14_remaining_time_exactly_24_hours_is_full_refund(service, monkeypatch):
    # BR14 – Remaining time must be calculated in exact hours, with no rounding
    now = datetime(2026, 1, 12, 0, 0, 0)
    monkeypatch.setattr("reservation_system.datetime", _freeze_datetime(now), raising=False)

    r = service.createReservation(flightId="F_EXACT_24H", seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)

    result = service.cancelReservation(reservationId=r.id)
    assert getattr(result, "refund", None) == "FULL"


def test_br14_remaining_time_23_hours_59_minutes_is_no_refund(service, monkeypatch):
    # BR14 – Remaining time must be calculated in exact hours, with no rounding
    now = datetime(2026, 1, 12, 0, 0, 0)
    monkeypatch.setattr("reservation_system.datetime", _freeze_datetime(now), raising=False)

    r = service.createReservation(flightId="F_EXACT_23H59M", seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)

    result = service.cancelReservation(reservationId=r.id)
    assert getattr(result, "refund", None) == "NONE"


# -----------------------------
# BR15 – use exclusively internally stored flight date/time as temporal reference
# -----------------------------

def test_br15_cancel_refund_policy_independent_of_external_time_source(service, monkeypatch):
    # BR15 – The system must use exclusively the internally stored flight date and time as the temporal reference
    # This test asserts that changing the process 'now' does not alter the computed policy outcome
    # when the flight's internally stored dateTime is the governing reference.
    now_a = datetime(2026, 1, 12, 0, 0, 0)
    now_b = datetime(2026, 1, 12, 5, 0, 0)

    r1 = service.createReservation(flightId="F_INT_TIME_REF", seat=1)
    service.confirmPayment(reservationId=r1.id, paymentApproved=True)

    monkeypatch.setattr("reservation_system.datetime", _freeze_datetime(now_a), raising=False)
    result_a = service.cancelReservation(reservationId=r1.id)

    r2 = service.createReservation(flightId="F_INT_TIME_REF", seat=2)
    service.confirmPayment(reservationId=r2.id, paymentApproved=True)

    monkeypatch.setattr("reservation_system.datetime", _freeze_datetime(now_b), raising=False)
    result_b = service.cancelReservation(reservationId=r2.id)

    assert getattr(result_a, "refund", None) == getattr(result_b, "refund", None)


# -----------------------------
# BR16 – flight dates/times/identifiers must not be altered after confirmation
# -----------------------------

def test_br16_flight_identifier_cannot_be_changed_after_confirmation(service):
    # BR16 – Flight dates, times, and identifiers must not be altered after reservation confirmation
    r = service.createReservation(flightId="F1", seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)

    with pytest.raises(Exception):
        # No API is specified for changing flightId; any attempt via a hypothetical method must be rejected.
        service.changeReservationFlight(reservationId=r.id, newFlightId="F2")  # type: ignore[attr-defined]
    assert r.state == "CONFIRMED"


# -----------------------------
# BR17 – indirect modification of flight data prohibited (reference swapping/cloning/recreation)
# -----------------------------

def test_br17_indirect_flight_data_modification_is_rejected(service):
    # BR17 – Indirect modifications of flight data are prohibited
    r = service.createReservation(flightId="F1", seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)

    with pytest.raises(Exception):
        # No API specified; any provided method enabling flight object replacement must be rejected.
        service.swapFlightObjectForReservation(reservationId=r.id, flightObject=object())  # type: ignore[attr-defined]
    assert r.state == "CONFIRMED"


# -----------------------------
# BR18 – each reservation may have exactly one associated payment
# -----------------------------

def test_br18_reservation_allows_exactly_one_payment(service):
    # BR18 – Each reservation may have exactly one associated payment
    r = service.createReservation(flightId="F1", seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)
    assert r.state == "CONFIRMED"


# -----------------------------
# BR19 – additional payment attempts must be rejected
# -----------------------------

def test_br19_second_payment_attempt_rejected(service):
    # BR19 – Additional payment attempts for the same reservation must be rejected
    r = service.createReservation(flightId="F1", seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)

    with pytest.raises(Exception):
        service.confirmPayment(reservationId=r.id, paymentApproved=True)

    assert r.state == "CONFIRMED"


# -----------------------------
# BR20 – payments not accepted for canceled reservations or after flight date
# -----------------------------

def test_br20_payment_not_accepted_for_canceled_reservation(service):
    # BR20 – Payments must not be accepted for canceled reservations
    r = service.createReservation(flightId="F1", seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)
    service.cancelReservation(reservationId=r.id)

    with pytest.raises(Exception):
        service.confirmPayment(reservationId=r.id, paymentApproved=True)
    assert r.state == "CANCELED"


def test_br20_payment_not_accepted_after_flight_date(service, monkeypatch):
    # BR20 – Payments must not be accepted after the flight date
    # Assumes flight dateTime is internally stored and can be in the past relative to the system's current time.
    now_after = datetime(2026, 1, 12, 0, 0, 0) + timedelta(days=10)
    monkeypatch.setattr("reservation_system.datetime", _freeze_datetime(now_after), raising=False)

    r = service.createReservation(flightId="F_PAST_FLIGHT", seat=1)
    with pytest.raises(Exception):
        service.confirmPayment(reservationId=r.id, paymentApproved=True)
    assert r.state == "CREATED"


# -----------------------------
# BR21 – determinism: same inputs sequence => same result
# -----------------------------

def test_br21_determinism_same_sequence_produces_same_states(service):
    # BR21 – System operations must be deterministic
    r1 = service.createReservation(flightId="F_DET", seat=1)
    service.confirmPayment(reservationId=r1.id, paymentApproved=True)
    service.cancelReservation(reservationId=r1.id)

    r2 = service.createReservation(flightId="F_DET", seat=1)
    service.confirmPayment(reservationId=r2.id, paymentApproved=True)
    service.cancelReservation(reservationId=r2.id)

    assert r1.state == r2.state == "CANCELED"


# -----------------------------
# BR22 – no implicit/unspecified behaviors
# -----------------------------

def test_br22_cancel_does_not_auto_rebook_or_create_new_reservation(service):
    # BR22 – The system must not assume unspecified implicit behaviors (e.g., automatic rebooking)
    r = service.createReservation(flightId="F1", seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)
    service.cancelReservation(reservationId=r.id)

    # The only specified effect is cancellation and seat release; no auto-created reservation must exist.
    # With no API to list reservations specified, we assert only that the canceled reservation remains canceled.
    assert r.state == "CANCELED"


# -----------------------------
# BR23 – violations fail immediately with no state change or partial records
# -----------------------------

def test_br23_violation_fails_immediately_and_does_not_change_state(service):
    # BR23 – Any business rule violation must result in immediate failure, with no state change
    r = service.createReservation(flightId="F1", seat=1)
    with pytest.raises(Exception):
        service.confirmPayment(reservationId=r.id, paymentApproved=False)
    assert r.state == "CREATED"


# -----------------------------
# BR24 – each valid operation generates exactly one immutable record
# -----------------------------

def test_br24_valid_operation_generates_exactly_one_immutable_record(service):
    # BR24 – Each valid operation must generate exactly one immutable record
    r = service.createReservation(flightId="F1", seat=1)

    record_before = service.getRecordCount()  # type: ignore[attr-defined]
    service.confirmPayment(reservationId=r.id, paymentApproved=True)
    record_after = service.getRecordCount()  # type: ignore[attr-defined]

    assert record_after - record_before == 1


# -----------------------------
# BR25 – failed operations must not generate persistent records
# -----------------------------

def test_br25_failed_operation_generates_no_persistent_record(service):
    # BR25 – Failed operations must not generate persistent records
    r = service.createReservation(flightId="F1", seat=1)

    record_before = service.getRecordCount()  # type: ignore[attr-defined]
    with pytest.raises(Exception):
        service.confirmPayment(reservationId=r.id, paymentApproved=False)
    record_after = service.getRecordCount()  # type: ignore[attr-defined]

    assert record_after == record_before


# -----------------------------
# BR26 – operations on one reservation must not affect others
# -----------------------------

def test_br26_cancel_one_reservation_does_not_affect_other_reservation(service):
    # BR26 – Operations performed on one reservation must not affect other reservations
    r1 = service.createReservation(flightId="F1", seat=1)
    r2 = service.createReservation(flightId="F1", seat=2)

    service.confirmPayment(reservationId=r1.id, paymentApproved=True)
    service.confirmPayment(reservationId=r2.id, paymentApproved=True)

    service.cancelReservation(reservationId=r1.id)

    assert r1.state == "CANCELED"
    assert r2.state == "CONFIRMED"


# -----------------------------
# FR01 – create initial reservation in CREATED associated with flight and available seat
# -----------------------------

def test_fr01_create_reservation_creates_created_state_with_seat(service):
    # FR01 – Create an initial reservation in the CREATED state, associated with a flight and an available seat
    r = service.createReservation(flightId="F1", seat=1)
    assert r.state == "CREATED"
    assert r.seat == 1


# -----------------------------
# FR02 – confirm payment and atomically confirm reservation
# -----------------------------

def test_fr02_confirm_payment_confirms_reservation_atomically(service):
    # FR02 – Confirm payment and, atomically, confirm the reservation
    r = service.createReservation(flightId="F1", seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)
    assert r.state == "CONFIRMED"


# -----------------------------
# FR03 – strictly control seat availability, ensuring exclusivity
# -----------------------------

def test_fr03_seat_exclusivity_enforced_at_reservation_creation(service):
    # FR03 – Strictly control seat availability, ensuring exclusivity per active reservation
    service.createReservation(flightId="F1", seat=1)
    with pytest.raises(Exception):
        service.createReservation(flightId="F1", seat=1)


# -----------------------------
# FR04 – cancel reservations respecting refund policy
# -----------------------------

def test_fr04_cancel_reservation_applies_refund_policy(service):
    # FR04 – Cancel reservations while strictly respecting refund policy
    r = service.createReservation(flightId="F_REFUND_POLICY", seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)

    result = service.cancelReservation(reservationId=r.id)
    assert getattr(result, "refund", None) in ("FULL", "NONE")


# -----------------------------
# FR05 – prevent invalid modification of state, flight data, seat, or payment
# -----------------------------

def test_fr05_invalid_state_modification_is_rejected(service):
    # FR05 – Prevent any invalid modification of state
    r = service.createReservation(flightId="F1", seat=1)
    with pytest.raises(Exception):
        # No direct setter specified; any provided method enabling manual state set must reject.
        service.setReservationState(reservationId=r.id, newState="CONFIRMED")  # type: ignore[attr-defined]
    assert r.state == "CREATED"


# -----------------------------
# FR06 – do not allow overbooking at any stage
# -----------------------------

def test_fr06_overbooking_prevented_on_seat_collision(service):
    # FR06 – Do not allow overbooking at any stage of the process
    service.createReservation(flightId="F1", seat=1)
    with pytest.raises(Exception):
        service.createReservation(flightId="F1", seat=1)


# -----------------------------
# FR07 – do not allow multiple, partial, or late payments
# -----------------------------

def test_fr07_partial_or_nonapproved_payment_is_rejected(service):
    # FR07 – Do not allow multiple, partial, or late payments
    r = service.createReservation(flightId="F1", seat=1)
    with pytest.raises(Exception):
        service.confirmPayment(reservationId=r.id, paymentApproved=False)
    assert r.state == "CREATED"


def test_fr07_multiple_payments_are_rejected(service):
    # FR07 – Do not allow multiple payments
    r = service.createReservation(flightId="F1", seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)
    with pytest.raises(Exception):
        service.confirmPayment(reservationId=r.id, paymentApproved=True)
    assert r.state == "CONFIRMED"


# -----------------------------
# FR08 – do not return intermediate states, explanatory messages, or partial results
# -----------------------------

def test_fr08_confirm_payment_does_not_return_intermediate_state(service):
    # FR08 – Do not return intermediate states, explanatory messages, or partial results
    r = service.createReservation(flightId="F1", seat=1)
    ret = service.confirmPayment(reservationId=r.id, paymentApproved=True)
    assert ret is None
    assert r.state == "CONFIRMED"


# -----------------------------
# FR09 – failures do not modify state or produce persistent side effects
# -----------------------------

def test_fr09_failed_confirm_payment_does_not_modify_state(service):
    # FR09 – Ensure that failures do not modify state
    r = service.createReservation(flightId="F1", seat=1)
    with pytest.raises(Exception):
        service.confirmPayment(reservationId=r.id, paymentApproved=False)
    assert r.state == "CREATED"


# -----------------------------
# FR10 – use exclusively provided and internally stored data; no inference/external enrichment
# -----------------------------

def test_fr10_create_reservation_uses_provided_flight_id_and_seat_only(service):
    # FR10 – Use exclusively provided and internally stored data
    r = service.createReservation(flightId="F_PROVIDED", seat=7)
    assert r.seat == 7
    assert getattr(r, "flightId", "F_PROVIDED") == "F_PROVIDED"
```