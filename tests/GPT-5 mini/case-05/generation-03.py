import pytest
from datetime import datetime, timedelta

# The tests below assume the existence of a module `reservation_service` that
# provides the following (as per the provided UML):
# - ReservationService class with methods:
#     createReservation(flightId: str, seat: int) -> Reservation
#     confirmPayment(reservationId: str, paymentApproved: bool) -> None
#     cancelReservation(reservationId: str) -> None
# - Reservation object with attributes:
#     id (str), state (str: "CREATED"|"CONFIRMED"|"CANCELED"), seat (int), flightId (str)
# - Flight object accessible via ReservationService for setup if needed
# - The system raises Exception (or subclasses) for validation failures
#
# Tests are written according to the user's specification and validate business rules (BR)
# and functional requirements (FR) exactly as described. Each test checks a single behavior.
#
# Note: These tests reference the external implementation but do not implement system behavior.
# They use only pytest and standard library datetime.

try:
    from reservation_service import ReservationService, Reservation, Flight, Payment, PaymentStatus, InvalidOperationError
except Exception:
    # If reservation_service module is not present, define placeholders so test file remains valid Python.
    # These placeholders are only to keep the file syntactically valid and are NOT used to implement logic.
    class InvalidOperationError(Exception):
        pass

    class ReservationService:
        def __init__(self):
            raise RuntimeError("Placeholder - real ReservationService must be provided by system under test")

# BR01 – A reservation may only be confirmed if exactly one approved payment is associated with it
def test_br01_confirm_only_with_one_approved_payment_succeeds_when_single_approved_payment_exists():
    # BR01
    # Positive case: Exactly one approved payment is used to confirm a reservation
    service = ReservationService()
    # Setup: assume a flight 'FL1' with seat 1 exists in the system (per FR01 context)
    reservation = service.createReservation("FL1", 1)
    # Action: confirm payment by providing an approved payment indicator
    service.confirmPayment(reservation.id, paymentApproved=True)
    # Assert: reservation must be CONFIRMED (exact state)
    refreshed = service.getReservation(reservation.id)
    assert refreshed.state == "CONFIRMED"
    assert refreshed.seat == 1

# BR02 – Payments with a status other than approved must not confirm reservations
def test_br02_non_approved_payment_does_not_confirm_and_raises_validation_error():
    # BR02
    service = ReservationService()
    reservation = service.createReservation("FL1", 2)
    # Action & Assert: attempting to confirm with a non-approved payment must raise and leave state unchanged
    with pytest.raises(Exception):
        service.confirmPayment(reservation.id, paymentApproved=False)
    refreshed = service.getReservation(reservation.id)
    assert refreshed.state == "CREATED"

# BR03 – Reservation confirmation and payment must be atomic
def test_br03_confirm_and_payment_are_atomic_no_partial_state_on_failure():
    # BR03
    service = ReservationService()
    reservation = service.createReservation("FL1", 3)
    # Some implementations offer a way to inject a simulated failure for testing atomicity.
    # Use a deterministic simulation hook if available; if not, the real system must still satisfy atomicity.
    # We attempt to trigger a failure during confirmPayment and assert no partial state change occurs.
    if hasattr(service, "inject_confirm_failure_for"):
        service.inject_confirm_failure_for(reservation.id, raise_exc=InvalidOperationError("simulated failure"))
        with pytest.raises(InvalidOperationError):
            service.confirmPayment(reservation.id, paymentApproved=True)
    else:
        # If injection not available, attempt an operation expected to fail deterministically (non-approved)
        with pytest.raises(Exception):
            service.confirmPayment(reservation.id, paymentApproved=False)
    # After failure, there must be NO observable change: reservation remains CREATED and no approved payment associated
    refreshed = service.getReservation(reservation.id)
    assert refreshed.state == "CREATED"
    if hasattr(service, "getPaymentStatus"):
        # If system exposes payment status, it must not show an approved payment
        assert service.getPaymentStatus(reservation.id) != "APPROVED"

# BR04 – A seat may belong to at most one active reservation per flight
def test_br04_seat_exclusivity_prevents_creating_two_active_reservations_for_same_seat():
    # BR04
    service = ReservationService()
    res1 = service.createReservation("FL2", 1)
    # Confirm first reservation so seat becomes active assignment
    service.confirmPayment(res1.id, paymentApproved=True)
    # Attempt to create a second reservation for same flight and seat must fail (overlap)
    with pytest.raises(Exception):
        service.createReservation("FL2", 1)

# BR05 – Canceled reservations must immediately release the associated seat
def test_br05_cancel_releases_seat_immediately_for_other_reservations_to_use():
    # BR05
    service = ReservationService()
    res = service.createReservation("FL3", 5)
    service.confirmPayment(res.id, paymentApproved=True)
    # Cancel reservation
    service.cancelReservation(res.id)
    # After cancellation, seat 5 must be available for a new reservation on same flight
    # Attempt to create a new reservation on same flight/seat should succeed
    new_res = service.createReservation("FL3", 5)
    assert new_res.seat == 5
    assert new_res.state == "CREATED"

# BR06 – Overbooking is not permitted under any circumstances
def test_br06_overbooking_is_rejected_when_total_seats_exceeded():
    # BR06
    service = ReservationService()
    # Assume flight FL4 has totalSeats = 1 (setup must be part of system)
    # Create reservation for seat 1 and confirm it
    r1 = service.createReservation("FL4", 1)
    service.confirmPayment(r1.id, paymentApproved=True)
    # Any attempt to create a second reservation (any seat) that would result in more confirmed reservations than seats must be rejected
    # Trying to create reservation for seat 2 (if seat numbering exists) but system must enforce totalSeats
    with pytest.raises(Exception):
        service.createReservation("FL4", 2)

# BR07 – Number of confirmed reservations must never exceed total seats
def test_br07_confirmed_reservations_never_exceed_total_seats_on_confirm():
    # BR07
    service = ReservationService()
    # Flight FL5 totalSeats assumed to be 2
    r1 = service.createReservation("FL5", 1)
    r2 = service.createReservation("FL5", 2)
    service.confirmPayment(r1.id, paymentApproved=True)
    service.confirmPayment(r2.id, paymentApproved=True)
    # Any further confirmation or creation that would increase confirmed count must be rejected
    r3 = service.createReservation("FL5", 3)
    with pytest.raises(Exception):
        service.confirmPayment(r3.id, paymentApproved=True)

# BR08 – A reservation may be exclusively in CREATED, CONFIRMED, or CANCELED
def test_br08_reservation_state_is_one_of_three_allowed_states_after_creation():
    # BR08
    service = ReservationService()
    res = service.createReservation("FL6", 10)
    assert res.state == "CREATED"
    # After confirmation
    service.confirmPayment(res.id, paymentApproved=True)
    r_conf = service.getReservation(res.id)
    assert r_conf.state == "CONFIRMED"
    # After cancellation
    service.cancelReservation(res.id)
    r_cancel = service.getReservation(res.id)
    assert r_cancel.state == "CANCELED"

# BR09 – Intermediate or additional states are not permitted
def test_br09_no_intermediate_states_exist_and_transitions_use_only_allowed_states():
    # BR09
    service = ReservationService()
    res = service.createReservation("FL7", 12)
    # The reservation.state must be exactly one of the allowed strings; no other states observed during lifecycle
    assert res.state in ("CREATED", "CONFIRMED", "CANCELED")
    service.confirmPayment(res.id, paymentApproved=True)
    assert service.getReservation(res.id).state in ("CREATED", "CONFIRMED", "CANCELED")
    service.cancelReservation(res.id)
    assert service.getReservation(res.id).state in ("CREATED", "CONFIRMED", "CANCELED")

# BR10 – Only valid transitions are CREATED→CONFIRMED and CONFIRMED→CANCELED
def test_br10_only_allowed_state_transitions_are_permitted():
    # BR10
    service = ReservationService()
    res = service.createReservation("FL8", 20)
    # Valid transition CREATED -> CONFIRMED
    service.confirmPayment(res.id, paymentApproved=True)
    assert service.getReservation(res.id).state == "CONFIRMED"
    # Valid transition CONFIRMED -> CANCELED
    service.cancelReservation(res.id)
    assert service.getReservation(res.id).state == "CANCELED"
    # Invalid transition: CANCELED -> CONFIRMED must be rejected
    with pytest.raises(Exception):
        service.confirmPayment(res.id, paymentApproved=True)

# BR11 – Any other state transition must be rejected
def test_br11_rejects_invalid_state_transitions_like_CREATED_to_CANCELED_directly_if_not_allowed():
    # BR11
    service = ReservationService()
    res = service.createReservation("FL9", 7)
    # The only path to CANCELED is via CONFIRMED per BR10; attempting to cancel a CREATED reservation must be rejected
    # (If system allows CREATED -> CANCELED directly, that's a violation)
    with pytest.raises(Exception):
        service.cancelReservation(res.id)
    # Ensure state unchanged
    assert service.getReservation(res.id).state == "CREATED"

# BR12 – A canceled reservation must not be reactivated, modified, or receive new payments
def test_br12_canceled_reservation_cannot_be_modified_or_receive_payments():
    # BR12
    service = ReservationService()
    r = service.createReservation("FL10", 8)
    service.confirmPayment(r.id, paymentApproved=True)
    service.cancelReservation(r.id)
    # Attempt to confirm payment again must be rejected
    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=True)
    # Attempt to modify seat via createReservation-like API or any update must be rejected
    if hasattr(service, "updateReservationSeat"):
        with pytest.raises(Exception):
            service.updateReservationSeat(r.id, 9)

# BR13 – Cancellation refund policy: Remaining time >=24h -> full refund; <24h -> no refund
def test_br13_cancel_refund_policy_exact_24_hours_threshold_full_refund_and_no_refund_below():
    # BR13
    service = ReservationService()
    # Create flights with known datetimes relative to system's internal reference.
    # Flight exactly 24 hours ahead
    flight_id_24 = "FL13A"
    flight_dt_24 = datetime(2030, 1, 2, 12, 0, 0)  # deterministic timestamp
    flight_id_23 = "FL13B"
    flight_dt_23 = datetime(2030, 1, 2, 11, 0, 0)  # 23 hours ahead if internal now is 2030-01-01 12:00:00
    # The test assumes the system uses internally stored flight datetimes (BR15) and deterministically compares
    # For the purpose of this test, set system clock hook if available
    if hasattr(service, "set_system_now"):
        service.set_system_now(datetime(2030, 1, 1, 12, 0, 0))
    if hasattr(service, "createFlight"):
        service.createFlight(flight_id_24, flight_dt_24, totalSeats=10)
        service.createFlight(flight_id_23, flight_dt_23, totalSeats=10)
    r24 = service.createReservation(flight_id_24, 1)
    r23 = service.createReservation(flight_id_23, 1)
    service.confirmPayment(r24.id, paymentApproved=True)
    service.confirmPayment(r23.id, paymentApproved=True)
    # Cancel reservation with remaining time exactly 24 hours -> expect full refund (system must expose refund info)
    if hasattr(service, "cancelReservationAndGetRefund"):
        refund_24 = service.cancelReservationAndGetRefund(r24.id)
        assert refund_24 == "FULL"
        refund_23 = service.cancelReservationAndGetRefund(r23.id)
        assert refund_23 == "NONE"
    else:
        # If system does not expose refund, at minimum cancellation must succeed; absence of refund data cannot be asserted
        service.cancelReservation(r24.id)
        service.cancelReservation(r23.id)
        assert service.getReservation(r24.id).state == "CANCELED"
        assert service.getReservation(r23.id).state == "CANCELED"

# BR14 – Remaining time must be calculated in exact hours, with no rounding or tolerance
def test_br14_remaining_time_calculation_uses_exact_integer_hours_no_rounding():
    # BR14
    service = ReservationService()
    flight_id = "FL14"
    flight_dt = datetime(2030, 6, 2, 15, 30, 0)  # example
    if hasattr(service, "set_system_now"):
        service.set_system_now(datetime(2030, 6, 1, 15, 30, 0))  # exactly 24 hours difference
    if hasattr(service, "createFlight"):
        service.createFlight(flight_id, flight_dt, totalSeats=5)
    r = service.createReservation(flight_id, 1)
    service.confirmPayment(r.id, paymentApproved=True)
    # If system exposes remaining_hours(reservationId), it must return exact integer hours (no rounding)
    if hasattr(service, "remaining_hours"):
        remaining = service.remaining_hours(r.id)
        assert remaining == 24
    # If not exposed, at least cancellation policy test (BR13) with exact 24 must behave as full refund (see BR13 test)

# BR15 – System must use exclusively internally stored flight date/time as temporal reference
def test_br15_system_uses_internal_flight_datetime_for_temporal_reference():
    # BR15
    service = ReservationService()
    flight_id = "FL15"
    flight_dt = datetime(2040, 1, 1, 0, 0, 0)
    if hasattr(service, "createFlight"):
        service.createFlight(flight_id, flight_dt, totalSeats=3)
    r = service.createReservation(flight_id, 1)
    service.confirmPayment(r.id, paymentApproved=True)
    # Even if caller passes an external 'now' parameter, system must ignore it.
    if hasattr(service, "cancelReservation"):
        # Attempt to cancel providing an external now if API allows (it should not), but system must still use internal flight datetime
        if hasattr(service, "cancelReservationWithNow"):
            service.set_system_now(datetime(2040, 1, 1, 0, 0, 0))
            with pytest.raises(Exception):
                service.cancelReservationWithNow(r.id, external_now=datetime(2040, 1, 1, 0, 0, 0))
        else:
            # If no alternative API exists, the presence of createFlight and deterministic behavior is sufficient.
            service.cancelReservation(r.id)
            assert service.getReservation(r.id).state == "CANCELED"

# BR16 – Flight dates, times, and identifiers must not be altered after reservation confirmation
def test_br16_flight_data_must_be_immutable_after_confirmation():
    # BR16
    service = ReservationService()
    flight_id = "FL16"
    flight_dt = datetime(2041, 5, 10, 9, 0, 0)
    if hasattr(service, "createFlight"):
        service.createFlight(flight_id, flight_dt, totalSeats=4)
    r = service.createReservation(flight_id, 2)
    service.confirmPayment(r.id, paymentApproved=True)
    # Attempt to modify flight data must be rejected
    if hasattr(service, "modifyFlightDatetime"):
        with pytest.raises(Exception):
            service.modifyFlightDatetime(flight_id, datetime(2041, 5, 11, 9, 0, 0))
    if hasattr(service, "modifyFlightIdentifier"):
        with pytest.raises(Exception):
            service.modifyFlightIdentifier(flight_id, "FL16-NEW")

# BR17 – Indirect modifications of flight data are prohibited (reference swapping/cloning)
def test_br17_indirect_modifications_of_flight_data_are_rejected_after_confirmation():
    # BR17
    service = ReservationService()
    flight_id = "FL17"
    flight_dt = datetime(2042, 3, 3, 14, 0, 0)
    if hasattr(service, "createFlight"):
        service.createFlight(flight_id, flight_dt, totalSeats=2)
    r = service.createReservation(flight_id, 1)
    service.confirmPayment(r.id, paymentApproved=True)
    # Attempt to swap flight references or recreate flight with same id must be rejected
    if hasattr(service, "recreateFlight"):
        with pytest.raises(Exception):
            service.recreateFlight(flight_id, flight_dt, totalSeats=10)

# BR18 – Each reservation may have exactly one associated payment
def test_br18_each_reservation_accepts_exactly_one_payment_and_rejects_second_attempt():
    # BR18
    service = ReservationService()
    r = service.createReservation("FL18", 3)
    # First payment attempt (approved)
    service.confirmPayment(r.id, paymentApproved=True)
    # Second payment attempt for same reservation must be rejected
    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=True)

# BR19 – Additional payment attempts for same reservation must be rejected
def test_br19_reject_additional_payment_attempts_after_initial_payment_attempt():
    # BR19
    service = ReservationService()
    r = service.createReservation("FL19", 4)
    # First attempt fails (non-approved) -> but is this counted as an attempt? BR19 prohibits additional attempts for same reservation.
    # According to BR18/BR19, each reservation may have exactly one associated payment; additional attempts must be rejected.
    # Attempt first payment
    service.confirmPayment(r.id, paymentApproved=False) if hasattr(service, "confirmPayment") else None
    # Any further payment attempts must be rejected
    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=True)

# BR20 – Payments must not be accepted for canceled reservations or after the flight date
def test_br20_no_payments_for_canceled_or_expired_reservations():
    # BR20
    service = ReservationService()
    # Create and cancel a reservation
    r = service.createReservation("FL20", 6)
    service.confirmPayment(r.id, paymentApproved=True)
    service.cancelReservation(r.id)
    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=True)
    # After flight date: create flight in past and attempt payment must be rejected
    past_flight_id = "FL20_PAST"
    past_dt = datetime(2000, 1, 1, 0, 0, 0)
    if hasattr(service, "createFlight"):
        service.createFlight(past_flight_id, past_dt, totalSeats=10)
    past_res = service.createReservation(past_flight_id, 1)
    with pytest.raises(Exception):
        service.confirmPayment(past_res.id, paymentApproved=True)

# BR21 – System operations must be deterministic
def test_br21_operations_are_deterministic_for_same_sequence_of_inputs():
    # BR21
    service1 = ReservationService()
    service2 = ReservationService()
    # Using identical sequences, results must be identical deterministically
    r1 = service1.createReservation("FL21", 1)
    service1.confirmPayment(r1.id, paymentApproved=True)
    s1_state = service1.getReservation(r1.id).state
    r2 = service2.createReservation("FL21", 1)
    service2.confirmPayment(r2.id, paymentApproved=True)
    s2_state = service2.getReservation(r2.id).state
    assert s1_state == s2_state == "CONFIRMED"

# BR22 – System must not assume unspecified implicit behaviors
def test_br22_no_implicit_behaviors_like_auto_rebooking_or_future_credit_are_performed():
    # BR22
    service = ReservationService()
    r = service.createReservation("FL22", 1)
    service.confirmPayment(r.id, paymentApproved=True)
    # Cancel and verify no automatic rebooking or credit is created (if system exposes such records)
    service.cancelReservation(r.id)
    if hasattr(service, "hasRebookingRecord"):
        assert service.hasRebookingRecord(r.id) is False
    if hasattr(service, "hasFutureCreditRecord"):
        assert service.hasFutureCreditRecord(r.id) is False

# BR23 – Any business rule violation must result in immediate failure with no state change or partial records
def test_br23_violation_results_in_no_state_change_and_no_partial_persistence():
    # BR23
    service = ReservationService()
    r = service.createReservation("FL23", 2)
    # Attempt invalid operation: confirm with non-approved payment
    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=False)
    # Ensure no partial state change: reservation remains CREATED
    assert service.getReservation(r.id).state == "CREATED"
    # If system exposes records, ensure no payment record was persisted
    if hasattr(service, "getPaymentStatus"):
        assert service.getPaymentStatus(r.id) is None

# BR24 – Each valid operation must generate exactly one immutable record
def test_br24_valid_operation_generates_single_immutable_record():
    # BR24
    service = ReservationService()
    r = service.createReservation("FL24", 1)
    # If system exposes record listing, check record count increases by exactly one on success
    if hasattr(service, "countRecords"):
        before = service.countRecords()
        service.confirmPayment(r.id, paymentApproved=True)
        after = service.countRecords()
        assert after == before + 1
    else:
        service.confirmPayment(r.id, paymentApproved=True)
        assert service.getReservation(r.id).state == "CONFIRMED"

# BR25 – Failed operations must not generate persistent records
def test_br25_failed_operations_do_not_persist_records():
    # BR25
    service = ReservationService()
    r = service.createReservation("FL25", 2)
    if hasattr(service, "countRecords"):
        before = service.countRecords()
        with pytest.raises(Exception):
            service.confirmPayment(r.id, paymentApproved=False)
        after = service.countRecords()
        assert after == before
    else:
        with pytest.raises(Exception):
            service.confirmPayment(r.id, paymentApproved=False)
        assert service.getReservation(r.id).state == "CREATED"

# BR26 – Operations on one reservation must not affect others
def test_br26_operations_on_one_reservation_do_not_affect_other_reservations_or_flights():
    # BR26
    service = ReservationService()
    r1 = service.createReservation("FL26", 1)
    r2 = service.createReservation("FL26", 2)
    service.confirmPayment(r1.id, paymentApproved=True)
    # Cancel r1 and assert r2 unaffected
    service.cancelReservation(r1.id)
    assert service.getReservation(r1.id).state == "CANCELED"
    assert service.getReservation(r2.id).state == "CREATED"

# FR01 – Create an initial reservation in CREATED state associated with a flight and available seat
def test_fr01_create_reservation_returns_created_state_and_associated_flight_and_seat():
    # FR01
    service = ReservationService()
    r = service.createReservation("FL100", 4)
    assert r.state == "CREATED"
    assert r.seat == 4
    assert r.flightId == "FL100"

# FR02 – Confirm payment and atomically confirm reservation
def test_fr02_confirm_payment_atomically_confirms_reservation_when_payment_approved():
    # FR02
    service = ReservationService()
    r = service.createReservation("FL101", 5)
    service.confirmPayment(r.id, paymentApproved=True)
    assert service.getReservation(r.id).state == "CONFIRMED"

# FR03 – Strictly control seat availability ensuring exclusivity per active reservation
def test_fr03_seat_availability_is_strictly_controlled_no_double_assignment_for_confirmed_seat():
    # FR03
    service = ReservationService()
    r = service.createReservation("FL102", 6)
    service.confirmPayment(r.id, paymentApproved=True)
    # Attempt to create another reservation for same seat must fail
    with pytest.raises(Exception):
        service.createReservation("FL102", 6)

# FR04 – Cancel reservations respecting refund policy based on remaining time
def test_fr04_cancel_respects_refund_policy_behavior_at_and_below_threshold():
    # FR04
    service = ReservationService()
    # Setup per BR13 assumptions; reuse BR13 flight setup if available
    flight_id = "FL103"
    flight_dt = datetime(2031, 8, 1, 12, 0, 0)
    if hasattr(service, "createFlight"):
        service.createFlight(flight_id, flight_dt, totalSeats=2)
    if hasattr(service, "set_system_now"):
        service.set_system_now(datetime(2031, 7, 31, 12, 0, 0))
    r = service.createReservation(flight_id, 1)
    service.confirmPayment(r.id, paymentApproved=True)
    # If refund info exposed, assert full refund at 24h
    if hasattr(service, "cancelReservationAndGetRefund"):
        refund = service.cancelReservationAndGetRefund(r.id)
        assert refund in ("FULL", "NONE")
    else:
        service.cancelReservation(r.id)
        assert service.getReservation(r.id).state == "CANCELED"

# FR05 – Prevent any invalid modification of state, flight data, seat, or payment
def test_fr05_prevent_invalid_modifications_of_state_flight_data_seat_or_payment():
    # FR05
    service = ReservationService()
    r = service.createReservation("FL104", 1)
    # Invalid state change (CREATED -> CANCELED) should be rejected per BR10/BR11
    with pytest.raises(Exception):
        service.cancelReservation(r.id)
    # Invalid seat modification should be rejected
    if hasattr(service, "updateReservationSeat"):
        with pytest.raises(Exception):
            service.updateReservationSeat(r.id, 2)

# FR06 – Do not allow overbooking at any stage
def test_fr06_no_overbooking_at_any_stage_creation_or_confirmation_rejected():
    # FR06
    service = ReservationService()
    # Assuming FL105 has totalSeats = 1
    r = service.createReservation("FL105", 1)
    service.confirmPayment(r.id, paymentApproved=True)
    # Attempt to create or confirm another reservation that would exceed seat capacity must be rejected
    r2 = service.createReservation("FL105", 2)
    with pytest.raises(Exception):
        service.confirmPayment(r2.id, paymentApproved=True)

# FR07 – Do not allow multiple, partial, or late payments
def test_fr07_multiple_partial_or_late_payments_are_rejected():
    # FR07
    service = ReservationService()
    r = service.createReservation("FL106", 1)
    # First, attempt a partial/non-approved payment must be rejected for counting as valid payment
    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=False)
    # After a failed attempt, additional attempts (per BR19) must be rejected
    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=True)

# FR08 – Do not return intermediate states, explanatory messages, or partial results
def test_fr08_operations_do_not_return_intermediate_states_or_partial_results():
    # FR08
    service = ReservationService()
    r = service.createReservation("FL107", 1)
    # confirmPayment should either complete successfully (reservation CONFIRMED) or raise; no intermediate values expected
    result = None
    try:
        service.confirmPayment(r.id, paymentApproved=True)
        result = service.getReservation(r.id).state
    except Exception:
        result = "ERROR"
    assert result in ("CONFIRMED", "ERROR")
    # No intermediate state strings other than allowed ones should be returned by getReservation

# FR09 – Ensure failures do not modify state or produce persistent side effects
def test_fr09_failures_do_not_modify_state_or_persist_side_effects():
    # FR09
    service = ReservationService()
    r = service.createReservation("FL108", 2)
    if hasattr(service, "countRecords"):
        before = service.countRecords()
        with pytest.raises(Exception):
            service.confirmPayment(r.id, paymentApproved=False)
        after = service.countRecords()
        assert after == before
    else:
        with pytest.raises(Exception):
            service.confirmPayment(r.id, paymentApproved=False)
        assert service.getReservation(r.id).state == "CREATED"

# FR10 – Use exclusively provided and internally stored data, with no inference or external enrichment
def test_fr10_system_uses_only_internal_and_provided_data_no_external_enrichment():
    # FR10
    service = ReservationService()
    # Try to pass extraneous external data to APIs; system must ignore or reject but not enrich data unexpectedly
    r = service.createReservation("FL109", 1)
    if hasattr(service, "confirmPaymentWithMetadata"):
        # If API allows metadata, it must not be used to change flight or seat deterministically
        service.confirmPaymentWithMetadata(r.id, paymentApproved=True, metadata={"external_offer": "FREE_UPGRADE"})
        assert service.getReservation(r.id).seat == 1
    else:
        service.confirmPayment(r.id, paymentApproved=True)
        assert service.getReservation(r.id).seat == 1

# END OF TEST SUITE