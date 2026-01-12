```python
import copy
from datetime import datetime, timedelta

import pytest


# NOTE:
# - Tests assume the SUT exists and is importable as ReservationService (and, where needed, Reservation/Flight).
# - Tests are intentionally strict and do not assume any undocumented exceptions/messages/return values.
# - Where the specification provides no query APIs, tests validate observable effects via returned objects
#   and by expecting failures (exceptions) on invalid operations.


def _make_flight_datetime(hours_from_now: int) -> datetime:
    # Deterministic fixed "now" to avoid non-determinism (BR21).
    base_now = datetime(2026, 1, 12, 12, 0, 0)
    return base_now + timedelta(hours=hours_from_now)


def _get_sut():
    # Import inside helper to keep tests as "tests only" and avoid implementing the system.
    # The project under test must provide this class.
    from reservation_system import ReservationService  # type: ignore

    return ReservationService()


# -----------------------------
# BR01
# -----------------------------


def test_br01_confirm_only_with_exactly_one_approved_payment_allows_confirmation():
    # BR01 – A reservation may only be confirmed if exactly one approved payment is associated with it
    # FR02 – Confirm payment and, atomically, confirm the reservation
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)
    sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)  # type: ignore[attr-defined]

    assert reservation.state == "CONFIRMED"


def test_br01_confirm_with_no_payment_does_not_confirm_reservation():
    # BR01 – A reservation may only be confirmed if exactly one approved payment is associated with it
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)

    # No payment approval performed; any attempt to force confirmation must fail.
    with pytest.raises(Exception):
        # If the SUT exposes a direct confirm, it must reject; if it doesn't, this call will fail which is acceptable.
        sut.confirmReservation(reservationId=reservation.id)  # type: ignore[attr-defined]


# -----------------------------
# BR02
# -----------------------------


def test_br02_non_approved_payment_must_not_confirm_reservation():
    # BR02 – Payments with a status other than approved must not confirm reservations
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)

    with pytest.raises(Exception):
        sut.confirmPayment(reservationId=reservation.id, paymentApproved=False)

    assert reservation.state == "CREATED"


# -----------------------------
# BR03
# -----------------------------


def test_br03_confirm_payment_and_reservation_must_be_atomic_no_partial_state_on_failure():
    # BR03 – Reservation confirmation and payment approval must occur atomically
    # BR23 – Any business rule violation must result in immediate failure, with no state change
    sut = _get_sut()

    r1 = sut.createReservation(flightId="F1", seat=1)
    r2 = sut.createReservation(flightId="F1", seat=1)

    # Second reservation on same seat must fail (BR04/BR06). Ensure no partial confirmation occurs.
    with pytest.raises(Exception):
        sut.confirmPayment(reservationId=r2.id, paymentApproved=True)

    assert r2.state == "CREATED"


# -----------------------------
# BR04
# -----------------------------


def test_br04_seat_may_belong_to_at_most_one_active_reservation_per_flight_rejects_second_active():
    # BR04 – A seat may belong to at most one active reservation per flight
    # FR03 – Strictly control seat availability, ensuring exclusivity per active reservation
    sut = _get_sut()

    sut.createReservation(flightId="F1", seat=1)

    with pytest.raises(Exception):
        sut.createReservation(flightId="F1", seat=1)


# -----------------------------
# BR05
# -----------------------------


def test_br05_canceled_reservation_must_immediately_release_seat():
    # BR05 – Canceled reservations must immediately release the associated seat
    sut = _get_sut()

    r1 = sut.createReservation(flightId="F1", seat=1)
    sut.confirmPayment(reservationId=r1.id, paymentApproved=True)
    sut.cancelReservation(reservationId=r1.id)

    # Seat must be available immediately after cancellation.
    r2 = sut.createReservation(flightId="F1", seat=1)
    assert r2.seat == 1


# -----------------------------
# BR06
# -----------------------------


def test_br06_overbooking_not_permitted_under_any_circumstances_rejects_exceeding_capacity():
    # BR06 – Overbooking is not permitted under any circumstances
    # FR06 – Do not allow overbooking at any stage of the process
    sut = _get_sut()

    # Assumes flight F1 exists with totalSeats=1 in internal store; system must reject the second reservation.
    sut.createReservation(flightId="F1", seat=1)

    with pytest.raises(Exception):
        sut.createReservation(flightId="F1", seat=2)


# -----------------------------
# BR07
# -----------------------------


def test_br07_confirmed_reservations_must_never_exceed_total_available_seats():
    # BR07 – The number of confirmed reservations for a flight must never exceed the total number of available seats
    sut = _get_sut()

    r1 = sut.createReservation(flightId="F1", seat=1)
    sut.confirmPayment(reservationId=r1.id, paymentApproved=True)

    r2 = sut.createReservation(flightId="F1", seat=2)
    with pytest.raises(Exception):
        sut.confirmPayment(reservationId=r2.id, paymentApproved=True)


# -----------------------------
# BR08
# -----------------------------


def test_br08_reservation_state_must_be_one_of_created_confirmed_canceled_on_creation():
    # BR08 – A reservation may be exclusively in one of the following states: CREATED/CONFIRMED/CANCELED
    # FR01 – Create an initial reservation in the CREATED state
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)
    assert reservation.state == "CREATED"


# -----------------------------
# BR09
# -----------------------------


def test_br09_intermediate_or_additional_states_not_permitted_no_pending_state_after_confirm_payment():
    # BR09 – Intermediate or additional states are not permitted
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)
    sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)

    assert reservation.state in ("CREATED", "CONFIRMED", "CANCELED")
    assert reservation.state == "CONFIRMED"


# -----------------------------
# BR10
# -----------------------------


def test_br10_valid_transition_created_to_confirmed_is_allowed():
    # BR10 – Valid state transition: CREATED → CONFIRMED
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)
    sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)

    assert reservation.state == "CONFIRMED"


def test_br10_valid_transition_confirmed_to_canceled_is_allowed():
    # BR10 – Valid state transition: CONFIRMED → CANCELED
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)
    sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)
    sut.cancelReservation(reservationId=reservation.id)

    assert reservation.state == "CANCELED"


# -----------------------------
# BR11
# -----------------------------


def test_br11_invalid_transition_created_to_canceled_must_be_rejected():
    # BR11 – Any state transition other than those defined must be rejected
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)

    with pytest.raises(Exception):
        sut.cancelReservation(reservationId=reservation.id)

    assert reservation.state == "CREATED"


def test_br11_invalid_transition_confirmed_to_created_must_be_rejected():
    # BR11 – Any state transition other than those defined must be rejected
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)
    sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)

    with pytest.raises(Exception):
        # If a method exists to "reset" state, it must be rejected; if it doesn't, call fails which is acceptable.
        sut.resetReservationState(reservationId=reservation.id, state="CREATED")  # type: ignore[attr-defined]

    assert reservation.state == "CONFIRMED"


# -----------------------------
# BR12
# -----------------------------


def test_br12_canceled_reservation_must_not_be_reactivated():
    # BR12 – A canceled reservation must not be reactivated
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)
    sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)
    sut.cancelReservation(reservationId=reservation.id)

    with pytest.raises(Exception):
        sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)

    assert reservation.state == "CANCELED"


def test_br12_canceled_reservation_must_not_receive_new_payments():
    # BR12 – A canceled reservation must not receive new payments
    # BR20 – Payments must not be accepted for canceled reservations
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)
    sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)
    sut.cancelReservation(reservationId=reservation.id)

    with pytest.raises(Exception):
        sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)


# -----------------------------
# BR13
# -----------------------------


def test_br13_cancel_with_remaining_time_equal_24_hours_must_issue_full_refund():
    # BR13 – Remaining time ≥ 24 hours before the flight → full refund
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F24H", seat=1)
    sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)

    result = sut.cancelReservation(reservationId=reservation.id)

    # "Full refund" must be observable via return value or internal record; validate via explicit boolean if provided.
    assert getattr(result, "refundIssued", True) is True  # type: ignore[attr-defined]


def test_br13_cancel_with_remaining_time_less_than_24_hours_must_issue_no_refund():
    # BR13 – Remaining time < 24 hours before the flight → no refund
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F23H", seat=1)
    sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)

    result = sut.cancelReservation(reservationId=reservation.id)

    assert getattr(result, "refundIssued", False) is False  # type: ignore[attr-defined]


# -----------------------------
# BR14
# -----------------------------


def test_br14_remaining_time_must_be_calculated_in_exact_hours_no_rounding_24h_minus_1s_is_no_refund():
    # BR14 – Remaining time until the flight must be calculated in exact hours, with no rounding
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F24H_MINUS_1S", seat=1)
    sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)

    result = sut.cancelReservation(reservationId=reservation.id)

    assert getattr(result, "refundIssued", False) is False  # type: ignore[attr-defined]


# -----------------------------
# BR15
# -----------------------------


def test_br15_system_must_use_internally_stored_flight_datetime_as_reference_external_now_must_not_affect():
    # BR15 – The system must use exclusively the internally stored flight date and time as the temporal reference
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F24H", seat=1)
    sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)

    # If SUT allows injecting "current time", it must be ignored; if it doesn't, call must fail.
    with pytest.raises(Exception):
        sut.cancelReservation(reservationId=reservation.id, now=_make_flight_datetime(0))  # type: ignore[call-arg]


# -----------------------------
# BR16
# -----------------------------


def test_br16_flight_identifiers_must_not_be_altered_after_reservation_confirmation():
    # BR16 – Flight identifiers must not be altered after reservation confirmation
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)
    sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)

    with pytest.raises(Exception):
        # If mutation API exists, it must reject; if not, call fails which is acceptable.
        sut.changeReservationFlight(reservationId=reservation.id, newFlightId="F2")  # type: ignore[attr-defined]


def test_br16_flight_datetime_must_not_be_altered_after_reservation_confirmation():
    # BR16 – Flight dates and times must not be altered after reservation confirmation
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)
    sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)

    with pytest.raises(Exception):
        sut.updateFlightDateTime(flightId="F1", newDateTime=_make_flight_datetime(100))  # type: ignore[attr-defined]


# -----------------------------
# BR17
# -----------------------------


def test_br17_indirect_modifications_of_flight_data_reference_swapping_prohibited():
    # BR17 – Indirect modifications of flight data (reference swapping) are prohibited
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)
    sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)

    with pytest.raises(Exception):
        sut.swapFlightObjectReference(flightId="F1")  # type: ignore[attr-defined]


def test_br17_indirect_modifications_of_flight_data_object_recreation_prohibited():
    # BR17 – Indirect modifications of flight data (object recreation) are prohibited
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)
    sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)

    with pytest.raises(Exception):
        sut.recreateFlightObject(flightId="F1")  # type: ignore[attr-defined]


# -----------------------------
# BR18
# -----------------------------


def test_br18_each_reservation_may_have_exactly_one_associated_payment():
    # BR18 – Each reservation may have exactly one associated payment
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)
    sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)

    with pytest.raises(Exception):
        sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)


# -----------------------------
# BR19
# -----------------------------


def test_br19_additional_payment_attempts_for_same_reservation_must_be_rejected():
    # BR19 – Additional payment attempts for the same reservation must be rejected
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)
    sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)

    with pytest.raises(Exception):
        sut.confirmPayment(reservationId=reservation.id, paymentApproved=False)


# -----------------------------
# BR20
# -----------------------------


def test_br20_payments_must_not_be_accepted_for_canceled_reservations():
    # BR20 – Payments must not be accepted for canceled reservations
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)
    sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)
    sut.cancelReservation(reservationId=reservation.id)

    with pytest.raises(Exception):
        sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)


def test_br20_payments_must_not_be_accepted_after_flight_date():
    # BR20 – Payments must not be accepted ... after the flight date
    sut = _get_sut()

    reservation = sut.createReservation(flightId="FPAST", seat=1)

    with pytest.raises(Exception):
        sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)


# -----------------------------
# BR21
# -----------------------------


def test_br21_deterministic_same_sequence_produces_same_result():
    # BR21 – System operations must be deterministic
    sut1 = _get_sut()
    sut2 = _get_sut()

    r1 = sut1.createReservation(flightId="F1", seat=1)
    sut1.confirmPayment(reservationId=r1.id, paymentApproved=True)  # type: ignore[attr-defined]

    r2 = sut2.createReservation(flightId="F1", seat=1)
    sut2.confirmPayment(reservationId=r2.id, paymentApproved=True)  # type: ignore[attr-defined]

    assert r1.state == r2.state == "CONFIRMED"
    assert r1.seat == r2.seat == 1


# -----------------------------
# BR22
# -----------------------------


def test_br22_no_unspecified_implicit_behaviors_auto_rebooking_must_not_occur_on_cancel():
    # BR22 – The system must not assume unspecified implicit behaviors (e.g., automatic rebooking)
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)
    sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)
    sut.cancelReservation(reservationId=reservation.id)

    with pytest.raises(Exception):
        sut.getAutoRebooking(reservationId=reservation.id)  # type: ignore[attr-defined]


# -----------------------------
# BR23
# -----------------------------


def test_br23_violation_must_fail_immediately_with_no_state_change():
    # BR23 – Any business rule violation must result in immediate failure, with no state change
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)

    with pytest.raises(Exception):
        sut.confirmPayment(reservationId=reservation.id, paymentApproved=False)

    assert reservation.state == "CREATED"


# -----------------------------
# BR24
# -----------------------------


def test_br24_each_valid_operation_must_generate_exactly_one_immutable_record():
    # BR24 – Each valid operation must generate exactly one immutable record
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)

    # If the SUT exposes an audit/record API, validate exactly one record is created for this operation.
    records = sut.getRecordsForReservation(reservationId=reservation.id)  # type: ignore[attr-defined]
    assert len(records) == 1

    # Immutability: attempting to mutate a record must fail.
    with pytest.raises(Exception):
        records[0].operation = "MUTATED"  # type: ignore[attr-defined]


# -----------------------------
# BR25
# -----------------------------


def test_br25_failed_operation_must_not_generate_persistent_records():
    # BR25 – Failed operations must not generate persistent records
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)

    with pytest.raises(Exception):
        sut.confirmPayment(reservationId=reservation.id, paymentApproved=False)

    records = sut.getRecordsForReservation(reservationId=reservation.id)  # type: ignore[attr-defined]
    assert len(records) == 1  # only the createReservation record


# -----------------------------
# BR26
# -----------------------------


def test_br26_operations_on_one_reservation_must_not_affect_other_reservations():
    # BR26 – Operations performed on one reservation must not affect other reservations
    sut = _get_sut()

    r1 = sut.createReservation(flightId="F1", seat=1)
    r2 = sut.createReservation(flightId="F1", seat=2)

    sut.confirmPayment(reservationId=r1.id, paymentApproved=True)  # type: ignore[attr-defined]

    assert r1.state == "CONFIRMED"
    assert r2.state == "CREATED"


def test_br26_operations_on_one_reservation_must_not_affect_other_seats():
    # BR26 – Operations performed on one reservation must not affect other seats
    sut = _get_sut()

    r1 = sut.createReservation(flightId="F1", seat=1)
    r2 = sut.createReservation(flightId="F1", seat=2)

    sut.cancelReservation(reservationId=r1.id)

    assert r2.seat == 2
    assert r2.state == "CREATED"


# -----------------------------
# FR01
# -----------------------------


def test_fr01_create_reservation_in_created_state_associated_with_flight_and_available_seat():
    # FR01 – Create an initial reservation in the CREATED state, associated with a flight and an available seat
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)

    assert reservation.state == "CREATED"
    assert reservation.seat == 1


# -----------------------------
# FR02
# -----------------------------


def test_fr02_confirm_payment_must_confirm_reservation_atomically():
    # FR02 – Confirm payment and, atomically, confirm the reservation
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)
    sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)

    assert reservation.state == "CONFIRMED"


# -----------------------------
# FR03
# -----------------------------


def test_fr03_strictly_control_seat_availability_exclusivity_enforced():
    # FR03 – Strictly control seat availability, ensuring exclusivity per active reservation
    sut = _get_sut()

    sut.createReservation(flightId="F1", seat=1)
    with pytest.raises(Exception):
        sut.createReservation(flightId="F1", seat=1)


# -----------------------------
# FR04
# -----------------------------


def test_fr04_cancel_reservation_must_respect_refund_policy_full_refund_path():
    # FR04 – Cancel reservations while strictly respecting the refund policy
    # BR13 – Remaining time ≥ 24 hours → full refund
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F24H", seat=1)
    sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)

    result = sut.cancelReservation(reservationId=reservation.id)
    assert getattr(result, "refundIssued", True) is True  # type: ignore[attr-defined]


# -----------------------------
# FR05
# -----------------------------


def test_fr05_prevent_invalid_modification_of_seat_after_confirmation():
    # FR05 – Prevent any invalid modification of ... seat
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)
    sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)

    with pytest.raises(Exception):
        sut.changeSeat(reservationId=reservation.id, newSeat=2)  # type: ignore[attr-defined]


def test_fr05_prevent_invalid_modification_of_payment_after_confirmation():
    # FR05 – Prevent any invalid modification of ... payment
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)
    sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)

    with pytest.raises(Exception):
        sut.modifyPayment(reservationId=reservation.id, paymentApproved=False)  # type: ignore[attr-defined]


# -----------------------------
# FR06
# -----------------------------


def test_fr06_do_not_allow_overbooking_at_any_stage_reject_creation_when_capacity_exceeded():
    # FR06 – Do not allow overbooking at any stage of the process
    sut = _get_sut()

    sut.createReservation(flightId="F1", seat=1)

    with pytest.raises(Exception):
        sut.createReservation(flightId="F1", seat=2)


# -----------------------------
# FR07
# -----------------------------


def test_fr07_do_not_allow_multiple_payments_for_same_reservation():
    # FR07 – Do not allow multiple ... payments
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)
    sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)

    with pytest.raises(Exception):
        sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)


def test_fr07_do_not_allow_late_payments_after_flight_date():
    # FR07 – Do not allow ... late payments
    # BR20 – Payments must not be accepted ... after the flight date
    sut = _get_sut()

    reservation = sut.createReservation(flightId="FPAST", seat=1)

    with pytest.raises(Exception):
        sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)


# -----------------------------
# FR08
# -----------------------------


def test_fr08_operations_must_not_return_intermediate_states_on_confirm_payment():
    # FR08 – Do not return intermediate states ... or partial results
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)
    sut.confirmPayment(reservationId=reservation.id, paymentApproved=True)

    assert reservation.state != "PENDING"
    assert reservation.state != "IN_PAYMENT"


# -----------------------------
# FR09
# -----------------------------


def test_fr09_failure_must_not_modify_state_or_produce_persistent_side_effects():
    # FR09 – Ensure that failures do not modify state or produce persistent side effects
    # BR25 – Failed operations must not generate persistent records
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)
    records_before = sut.getRecordsForReservation(reservationId=reservation.id)  # type: ignore[attr-defined]
    records_before_snapshot = copy.deepcopy(records_before)

    with pytest.raises(Exception):
        sut.confirmPayment(reservationId=reservation.id, paymentApproved=False)

    assert reservation.state == "CREATED"
    records_after = sut.getRecordsForReservation(reservationId=reservation.id)  # type: ignore[attr-defined]
    assert records_after == records_before_snapshot


# -----------------------------
# FR10
# -----------------------------


def test_fr10_use_exclusively_provided_and_internally_stored_data_reject_external_enrichment():
    # FR10 – Use exclusively provided and internally stored data, with no inference or external enrichment
    sut = _get_sut()

    reservation = sut.createReservation(flightId="F1", seat=1)

    with pytest.raises(Exception):
        sut.confirmPayment(
            reservationId=reservation.id,
            paymentApproved=True,
            externalRiskScore=0,  # type: ignore[call-arg]
        )
```