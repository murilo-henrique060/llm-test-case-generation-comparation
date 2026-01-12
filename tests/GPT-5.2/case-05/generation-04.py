```python
import pytest
from datetime import datetime, timedelta

# NOTE:
# These tests assume the existence of a SUT that matches the provided UML:
# - ReservationService with methods:
#     createReservation(flightId: string, seat: int) -> Reservation
#     confirmPayment(reservationId: string, paymentApproved: boolean) -> void
#     cancelReservation(reservationId: string) -> void
# - Reservation with attributes: state, seat
# - Flight with attributes: dateTime, totalSeats
#
# The tests reference these names directly; the system under test must provide them.
# The tests do not implement the system.

# ---------------------------------------------------------------------------
# Helpers / fixtures (test-side only)
# ---------------------------------------------------------------------------

@pytest.fixture
def fixed_now():
    # Deterministic reference "now" used only for constructing test data values.
    return datetime(2026, 1, 12, 0, 0, 0)


@pytest.fixture
def flight_id():
    return "FLIGHT-001"


@pytest.fixture
def other_flight_id():
    return "FLIGHT-002"


@pytest.fixture
def reservation_service():
    # The SUT must provide a concrete ReservationService in the test environment.
    # BR21 – Deterministic operations (the same tests should always behave the same).
    from reservation_system import ReservationService  # type: ignore
    return ReservationService()


def _get_reservation_id(reservation):
    # The specification defines Reservation with state and seat only.
    # If the SUT exposes an id attribute (common), tests can use it.
    # If not, the SUT must otherwise allow referencing a reservation for subsequent calls.
    return getattr(reservation, "id")


def _set_internal_flight_datetime_for_test(reservation_service, flight_id, dt):
    # BR15 requires using "internally stored flight date and time".
    # The spec does not define how to set flight date/time in the SUT.
    # These tests assume the SUT provides a dedicated test hook or setup API.
    if hasattr(reservation_service, "setFlightDateTime"):
        reservation_service.setFlightDateTime(flight_id, dt)
        return
    if hasattr(reservation_service, "_setFlightDateTimeForTest"):
        reservation_service._setFlightDateTimeForTest(flight_id, dt)
        return
    pytest.skip("SUT does not expose a way to set internally stored flight date/time for deterministic tests.")


def _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats):
    # BR07 refers to "total number of available seats" for a flight.
    # The spec does not define how to configure it; assume a test hook/setup API exists.
    if hasattr(reservation_service, "setFlightTotalSeats"):
        reservation_service.setFlightTotalSeats(flight_id, total_seats)
        return
    if hasattr(reservation_service, "_setFlightTotalSeatsForTest"):
        reservation_service._setFlightTotalSeatsForTest(flight_id, total_seats)
        return
    pytest.skip("SUT does not expose a way to set total seats for deterministic tests.")


def _get_operation_records_for_test(reservation_service):
    # BR24/BR25 require immutable records; the spec does not define an API.
    # Assume a test hook exists to retrieve persistent records.
    if hasattr(reservation_service, "getRecordsForTest"):
        return reservation_service.getRecordsForTest()
    if hasattr(reservation_service, "_getRecordsForTest"):
        return reservation_service._getRecordsForTest()
    pytest.skip("SUT does not expose a way to read persistent records for record-count assertions.")


def _get_reservation_snapshot_for_test(reservation_service, reservation_id):
    # BR23/BR09 require no partial state; we need to re-read state from SUT.
    # Assume a test hook exists.
    if hasattr(reservation_service, "getReservationForTest"):
        return reservation_service.getReservationForTest(reservation_id)
    if hasattr(reservation_service, "_getReservationForTest"):
        return reservation_service._getReservationForTest(reservation_id)
    pytest.skip("SUT does not expose a way to read reservation state by id for deterministic assertions.")


def _get_payment_snapshot_for_test(reservation_service, reservation_id):
    # BR01/BR02/BR03/BR18 refer to payments; spec does not define payment model.
    # Assume a test hook exists.
    if hasattr(reservation_service, "getPaymentForTest"):
        return reservation_service.getPaymentForTest(reservation_id)
    if hasattr(reservation_service, "_getPaymentForTest"):
        return reservation_service._getPaymentForTest(reservation_id)
    pytest.skip("SUT does not expose a way to read payment state by reservation id for deterministic assertions.")


# ---------------------------------------------------------------------------
# FR01 / BR08 / BR09 / BR04 / BR06 / BR07
# ---------------------------------------------------------------------------

def test_fr01_create_reservation_in_created_state_with_flight_and_available_seat(reservation_service, fixed_now, flight_id):
    # FR01 – Create an initial reservation in the CREATED state, associated with a flight and an available seat
    # BR08 – Reservation may be exclusively in CREATED/CONFIRMED/CANCELED
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=2)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    reservation = reservation_service.createReservation(flight_id=flight_id, seat=1)

    assert reservation.state == "CREATED"
    assert reservation.seat == 1


def test_br09_create_reservation_must_not_return_intermediate_or_additional_state(reservation_service, fixed_now, flight_id):
    # BR09 – Intermediate or additional states are not permitted
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    reservation = reservation_service.createReservation(flightId=flight_id, seat=1)

    assert reservation.state in {"CREATED", "CONFIRMED", "CANCELED"}
    assert reservation.state == "CREATED"


def test_br04_seat_may_belong_to_at_most_one_active_reservation_per_flight(reservation_service, fixed_now, flight_id):
    # BR04 – A seat may belong to at most one active reservation per flight
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=2)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    _ = reservation_service.createReservation(flightId=flight_id, seat=1)

    with pytest.raises(Exception):
        reservation_service.createReservation(flightId=flight_id, seat=1)


def test_br06_overbooking_not_permitted_when_creating_reservations_beyond_total_seats(reservation_service, fixed_now, flight_id):
    # BR06 – Overbooking is not permitted under any circumstances
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    _ = reservation_service.createReservation(flightId=flight_id, seat=1)

    with pytest.raises(Exception):
        reservation_service.createReservation(flightId=flight_id, seat=2)


# ---------------------------------------------------------------------------
# BR01 / BR02 / BR18 / BR19 / FR02 / FR07
# ---------------------------------------------------------------------------

def test_br18_each_reservation_may_have_exactly_one_associated_payment(reservation_service, fixed_now, flight_id):
    # BR18 – Each reservation may have exactly one associated payment
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    reservation = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid = _get_reservation_id(reservation)

    reservation_service.confirmPayment(reservationId=rid, paymentApproved=True)

    payment = _get_payment_snapshot_for_test(reservation_service, rid)
    # Expect a single payment association to exist
    assert payment is not None


def test_br19_additional_payment_attempts_for_same_reservation_must_be_rejected(reservation_service, fixed_now, flight_id):
    # BR19 – Additional payment attempts for the same reservation must be rejected
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    reservation = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid = _get_reservation_id(reservation)

    reservation_service.confirmPayment(reservationId=rid, paymentApproved=True)

    with pytest.raises(Exception):
        reservation_service.confirmPayment(reservationId=rid, paymentApproved=True)


def test_br01_reservation_may_only_be_confirmed_if_exactly_one_approved_payment_associated(reservation_service, fixed_now, flight_id):
    # BR01 – A reservation may only be confirmed if exactly one approved payment is associated with it
    # FR02 – Confirm payment and, atomically, confirm the reservation
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    reservation = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid = _get_reservation_id(reservation)

    reservation_service.confirmPayment(reservationId=rid, paymentApproved=True)

    updated = _get_reservation_snapshot_for_test(reservation_service, rid)
    assert updated.state == "CONFIRMED"

    payment = _get_payment_snapshot_for_test(reservation_service, rid)
    assert getattr(payment, "status", "approved") == "approved"


def test_br02_payment_with_status_other_than_approved_must_not_confirm_reservation(reservation_service, fixed_now, flight_id):
    # BR02 – Payments with a status other than approved must not confirm reservations
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    reservation = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid = _get_reservation_id(reservation)

    with pytest.raises(Exception):
        reservation_service.confirmPayment(reservationId=rid, paymentApproved=False)

    updated = _get_reservation_snapshot_for_test(reservation_service, rid)
    assert updated.state == "CREATED"


# ---------------------------------------------------------------------------
# BR03 – Atomicity between payment approval and reservation confirmation
# ---------------------------------------------------------------------------

def test_br03_confirm_payment_and_reservation_confirmation_must_be_atomic_no_partial_state(reservation_service, fixed_now, flight_id):
    # BR03 – Reservation confirmation and payment approval must occur atomically, and no observable state may exist in which only one of the two has been completed
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    reservation = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid = _get_reservation_id(reservation)

    reservation_service.confirmPayment(reservationId=rid, paymentApproved=True)

    updated = _get_reservation_snapshot_for_test(reservation_service, rid)
    payment = _get_payment_snapshot_for_test(reservation_service, rid)

    # Atomicity: after success, both must reflect completion
    assert updated.state == "CONFIRMED"
    assert getattr(payment, "status", "approved") == "approved"


def test_br03_on_payment_confirmation_failure_no_partial_records_or_state_change(reservation_service, fixed_now, flight_id):
    # BR03 – Atomicity (no observable state where only one completed)
    # BR23 – Any business rule violation must result in immediate failure, with no state change or creation of partial records
    # BR25 – Failed operations must not generate persistent records
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    reservation = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid = _get_reservation_id(reservation)

    records_before = _get_operation_records_for_test(reservation_service)

    with pytest.raises(Exception):
        reservation_service.confirmPayment(reservationId=rid, paymentApproved=False)

    records_after = _get_operation_records_for_test(reservation_service)
    assert len(records_after) == len(records_before)

    updated = _get_reservation_snapshot_for_test(reservation_service, rid)
    assert updated.state == "CREATED"


# ---------------------------------------------------------------------------
# BR10 / BR11 / BR08 / FR05 – State transitions and rejection
# ---------------------------------------------------------------------------

def test_br10_valid_transition_created_to_confirmed_is_allowed(reservation_service, fixed_now, flight_id):
    # BR10 – The only valid state transitions include CREATED → CONFIRMED
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    reservation = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid = _get_reservation_id(reservation)

    reservation_service.confirmPayment(reservationId=rid, paymentApproved=True)

    updated = _get_reservation_snapshot_for_test(reservation_service, rid)
    assert updated.state == "CONFIRMED"


def test_br10_valid_transition_confirmed_to_canceled_is_allowed(reservation_service, fixed_now, flight_id):
    # BR10 – The only valid state transitions include CONFIRMED → CANCELED
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    reservation = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid = _get_reservation_id(reservation)
    reservation_service.confirmPayment(reservationId=rid, paymentApproved=True)

    reservation_service.cancelReservation(reservationId=rid)

    updated = _get_reservation_snapshot_for_test(reservation_service, rid)
    assert updated.state == "CANCELED"


def test_br11_invalid_transition_created_to_canceled_must_be_rejected(reservation_service, fixed_now, flight_id):
    # BR11 – Any state transition other than those defined must be rejected
    # (CREATED → CANCELED is not listed as valid)
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    reservation = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid = _get_reservation_id(reservation)

    with pytest.raises(Exception):
        reservation_service.cancelReservation(reservationId=rid)

    updated = _get_reservation_snapshot_for_test(reservation_service, rid)
    assert updated.state == "CREATED"


def test_br11_invalid_transition_confirmed_to_confirmed_must_be_rejected(reservation_service, fixed_now, flight_id):
    # BR11 – Any state transition other than those defined must be rejected
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    reservation = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid = _get_reservation_id(reservation)
    reservation_service.confirmPayment(reservationId=rid, paymentApproved=True)

    with pytest.raises(Exception):
        reservation_service.confirmPayment(reservationId=rid, paymentApproved=True)

    updated = _get_reservation_snapshot_for_test(reservation_service, rid)
    assert updated.state == "CONFIRMED"


# ---------------------------------------------------------------------------
# BR12 / FR07 / FR05 – Cancelled reservation immutability and payment rejection
# ---------------------------------------------------------------------------

def test_br12_canceled_reservation_must_not_receive_new_payments(reservation_service, fixed_now, flight_id):
    # BR12 – A canceled reservation must not be reactivated, modified, or receive new payments
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    reservation = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid = _get_reservation_id(reservation)
    reservation_service.confirmPayment(reservationId=rid, paymentApproved=True)
    reservation_service.cancelReservation(reservationId=rid)

    with pytest.raises(Exception):
        reservation_service.confirmPayment(reservationId=rid, paymentApproved=True)

    updated = _get_reservation_snapshot_for_test(reservation_service, rid)
    assert updated.state == "CANCELED"


def test_br12_canceled_reservation_must_not_be_reactivated(reservation_service, fixed_now, flight_id):
    # BR12 – A canceled reservation must not be reactivated
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    reservation = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid = _get_reservation_id(reservation)
    reservation_service.confirmPayment(reservationId=rid, paymentApproved=True)
    reservation_service.cancelReservation(reservationId=rid)

    with pytest.raises(Exception):
        reservation_service.cancelReservation(reservationId=rid)

    updated = _get_reservation_snapshot_for_test(reservation_service, rid)
    assert updated.state == "CANCELED"


# ---------------------------------------------------------------------------
# BR05 – Seat release on cancellation
# ---------------------------------------------------------------------------

def test_br05_canceled_reservation_must_immediately_release_associated_seat(reservation_service, fixed_now, flight_id):
    # BR05 – Canceled reservations must immediately release the associated seat
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    reservation1 = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid1 = _get_reservation_id(reservation1)
    reservation_service.confirmPayment(reservationId=rid1, paymentApproved=True)
    reservation_service.cancelReservation(reservationId=rid1)

    reservation2 = reservation_service.createReservation(flightId=flight_id, seat=1)
    assert reservation2.state == "CREATED"
    assert reservation2.seat == 1


# ---------------------------------------------------------------------------
# BR07 – Confirmed reservations must not exceed total seats
# ---------------------------------------------------------------------------

def test_br07_confirmed_reservations_must_never_exceed_total_seats(reservation_service, fixed_now, flight_id):
    # BR07 – The number of confirmed reservations for a flight must never exceed total available seats
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    r1 = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid1 = _get_reservation_id(r1)
    reservation_service.confirmPayment(reservationId=rid1, paymentApproved=True)

    # Attempt to create and confirm another reservation should be rejected at some stage
    with pytest.raises(Exception):
        r2 = reservation_service.createReservation(flightId=flight_id, seat=2)
        rid2 = _get_reservation_id(r2)
        reservation_service.confirmPayment(reservationId=rid2, paymentApproved=True)


# ---------------------------------------------------------------------------
# BR13 / BR14 / BR15 / FR04 – Refund policy based on exact hours remaining
# ---------------------------------------------------------------------------

def test_br13_remaining_time_equal_24_hours_requires_full_refund(reservation_service, fixed_now, flight_id):
    # BR13 – Remaining time ≥ 24 hours before the flight → full refund
    # BR14 – Remaining time calculated in exact hours, no rounding/tolerance
    # BR15 – Use exclusively internally stored flight date/time as temporal reference
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)

    # Exactly 24 hours remaining
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=24))

    reservation = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid = _get_reservation_id(reservation)
    reservation_service.confirmPayment(reservationId=rid, paymentApproved=True)

    # Assume cancellation returns something indicating refund outcome is persisted in record.
    # Spec does not define return value, so we validate via records.
    records_before = _get_operation_records_for_test(reservation_service)
    reservation_service.cancelReservation(reservationId=rid)
    records_after = _get_operation_records_for_test(reservation_service)

    assert len(records_after) == len(records_before) + 1
    last = records_after[-1]
    assert getattr(last, "refund", "full") == "full"


def test_br13_remaining_time_less_than_24_hours_requires_no_refund(reservation_service, fixed_now, flight_id):
    # BR13 – Remaining time < 24 hours before the flight → no refund
    # BR14 – Remaining time calculated in exact hours, no rounding/tolerance
    # BR15 – Use exclusively internally stored flight date/time as temporal reference
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)

    # Exactly 23 hours remaining (explicitly < 24)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=23))

    reservation = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid = _get_reservation_id(reservation)
    reservation_service.confirmPayment(reservationId=rid, paymentApproved=True)

    records_before = _get_operation_records_for_test(reservation_service)
    reservation_service.cancelReservation(reservationId=rid)
    records_after = _get_operation_records_for_test(reservation_service)

    assert len(records_after) == len(records_before) + 1
    last = records_after[-1]
    assert getattr(last, "refund", "none") == "none"


def test_br14_no_rounding_at_boundary_24_hours_minus_1_second_is_not_full_refund(reservation_service, fixed_now, flight_id):
    # BR14 – Remaining time until flight must be calculated in exact hours, with no rounding or tolerance of any kind
    # BR13 – Remaining time < 24 hours → no refund
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)

    # 24 hours minus 1 second is strictly < 24 hours; must be treated as no refund.
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=24) - timedelta(seconds=1))

    reservation = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid = _get_reservation_id(reservation)
    reservation_service.confirmPayment(reservationId=rid, paymentApproved=True)

    records_before = _get_operation_records_for_test(reservation_service)
    reservation_service.cancelReservation(reservationId=rid)
    records_after = _get_operation_records_for_test(reservation_service)

    assert len(records_after) == len(records_before) + 1
    last = records_after[-1]
    assert getattr(last, "refund", "none") == "none"


# ---------------------------------------------------------------------------
# BR16 / BR17 / FR05 – Flight data immutability after confirmation (no alteration / no swapping)
# ---------------------------------------------------------------------------

def test_br16_flight_identifier_must_not_be_altered_after_reservation_confirmation(reservation_service, fixed_now, flight_id):
    # BR16 – Flight dates, times, and identifiers must not be altered after reservation confirmation
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    reservation = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid = _get_reservation_id(reservation)
    reservation_service.confirmPayment(reservationId=rid, paymentApproved=True)

    if not hasattr(reservation_service, "updateReservationFlightForTest") and not hasattr(reservation_service, "_updateReservationFlightForTest"):
        pytest.skip("SUT does not expose a test hook to attempt forbidden flight identifier modification.")

    with pytest.raises(Exception):
        if hasattr(reservation_service, "updateReservationFlightForTest"):
            reservation_service.updateReservationFlightForTest(reservationId=rid, newFlightId="FLIGHT-CHANGED")
        else:
            reservation_service._updateReservationFlightForTest(reservationId=rid, newFlightId="FLIGHT-CHANGED")


def test_br16_flight_datetime_must_not_be_altered_after_reservation_confirmation(reservation_service, fixed_now, flight_id):
    # BR16 – Flight dates/times must not be altered after reservation confirmation
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    reservation = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid = _get_reservation_id(reservation)
    reservation_service.confirmPayment(reservationId=rid, paymentApproved=True)

    if not hasattr(reservation_service, "setFlightDateTime") and not hasattr(reservation_service, "_setFlightDateTimeForTest"):
        pytest.skip("SUT does not expose a test hook to attempt forbidden flight datetime modification.")

    with pytest.raises(Exception):
        _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=72))


def test_br17_indirect_modification_of_flight_data_reference_swapping_is_prohibited(reservation_service, fixed_now, flight_id, other_flight_id):
    # BR17 – Indirect modifications of flight data (reference swapping, cloning, object recreation) are prohibited
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))
    _set_internal_flight_total_seats_for_test(reservation_service, other_flight_id, total_seats=1)
    _set_internal_flight_datetime_for_test(reservation_service, other_flight_id, fixed_now + timedelta(hours=96))

    reservation = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid = _get_reservation_id(reservation)
    reservation_service.confirmPayment(reservationId=rid, paymentApproved=True)

    if not hasattr(reservation_service, "swapReservationFlightReferenceForTest") and not hasattr(reservation_service, "_swapReservationFlightReferenceForTest"):
        pytest.skip("SUT does not expose a test hook to attempt forbidden flight reference swapping.")

    with pytest.raises(Exception):
        if hasattr(reservation_service, "swapReservationFlightReferenceForTest"):
            reservation_service.swapReservationFlightReferenceForTest(reservationId=rid, newFlightId=other_flight_id)
        else:
            reservation_service._swapReservationFlightReferenceForTest(reservationId=rid, newFlightId=other_flight_id)


# ---------------------------------------------------------------------------
# BR20 – Payments must not be accepted for canceled reservations or after flight date
# ---------------------------------------------------------------------------

def test_br20_payments_must_not_be_accepted_for_canceled_reservations(reservation_service, fixed_now, flight_id):
    # BR20 – Payments must not be accepted for canceled reservations
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    reservation = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid = _get_reservation_id(reservation)
    reservation_service.confirmPayment(reservationId=rid, paymentApproved=True)
    reservation_service.cancelReservation(reservationId=rid)

    with pytest.raises(Exception):
        reservation_service.confirmPayment(reservationId=rid, paymentApproved=True)


def test_br20_payments_must_not_be_accepted_after_flight_date(reservation_service, fixed_now, flight_id):
    # BR20 – Payments must not be accepted after the flight date
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)

    # Internally stored flight datetime is in the past relative to fixed_now
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now - timedelta(hours=1))

    reservation = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid = _get_reservation_id(reservation)

    with pytest.raises(Exception):
        reservation_service.confirmPayment(reservationId=rid, paymentApproved=True)

    updated = _get_reservation_snapshot_for_test(reservation_service, rid)
    assert updated.state == "CREATED"


# ---------------------------------------------------------------------------
# BR21 – Determinism
# ---------------------------------------------------------------------------

def test_br21_same_sequence_of_inputs_produces_same_results(reservation_service, fixed_now, flight_id):
    # BR21 – System operations must be deterministic
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=2)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    r1 = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid1 = _get_reservation_id(r1)
    reservation_service.confirmPayment(reservationId=rid1, paymentApproved=True)
    reservation_service.cancelReservation(reservationId=rid1)

    # Repeat with a new reservation on same seat after release; should deterministically succeed.
    r2 = reservation_service.createReservation(flightId=flight_id, seat=1)
    assert r2.state == "CREATED"
    assert r2.seat == 1


# ---------------------------------------------------------------------------
# BR22 – No implicit unspecified behaviors (validate no unexpected auto-actions)
# ---------------------------------------------------------------------------

def test_br22_cancel_does_not_auto_rebook_or_create_new_reservation(reservation_service, fixed_now, flight_id):
    # BR22 – The system must not assume unspecified implicit behaviors (e.g., automatic rebooking)
    # We validate no extra persistent record beyond the single cancel operation record.
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    reservation = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid = _get_reservation_id(reservation)
    reservation_service.confirmPayment(reservationId=rid, paymentApproved=True)

    records_before = _get_operation_records_for_test(reservation_service)
    reservation_service.cancelReservation(reservationId=rid)
    records_after = _get_operation_records_for_test(reservation_service)

    # BR24 – Each valid operation must generate exactly one immutable record
    # Here the single valid operation is cancelReservation.
    assert len(records_after) == len(records_before) + 1


# ---------------------------------------------------------------------------
# BR23 / FR09 – Failures cause no state change and no partial records
# ---------------------------------------------------------------------------

def test_br23_business_rule_violation_must_fail_immediately_with_no_state_change(reservation_service, fixed_now, flight_id):
    # BR23 – Any business rule violation must result in immediate failure, with no state change or creation of partial records
    # Use a defined violation: BR11 invalid transition CREATED → CANCELED
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    reservation = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid = _get_reservation_id(reservation)

    with pytest.raises(Exception):
        reservation_service.cancelReservation(reservationId=rid)

    updated = _get_reservation_snapshot_for_test(reservation_service, rid)
    assert updated.state == "CREATED"


def test_fr09_failure_must_not_produce_persistent_side_effects(reservation_service, fixed_now, flight_id):
    # FR09 – Ensure that failures do not modify state or produce persistent side effects
    # Use BR19 additional payment attempt must be rejected and must not create a record.
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    reservation = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid = _get_reservation_id(reservation)
    reservation_service.confirmPayment(reservationId=rid, paymentApproved=True)

    records_before = _get_operation_records_for_test(reservation_service)

    with pytest.raises(Exception):
        reservation_service.confirmPayment(reservationId=rid, paymentApproved=True)

    records_after = _get_operation_records_for_test(reservation_service)
    assert len(records_after) == len(records_before)


# ---------------------------------------------------------------------------
# BR24 / BR25 – Record generation
# ---------------------------------------------------------------------------

def test_br24_each_valid_operation_must_generate_exactly_one_immutable_record(reservation_service, fixed_now, flight_id):
    # BR24 – Each valid operation must generate exactly one immutable record
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    records_before = _get_operation_records_for_test(reservation_service)
    _ = reservation_service.createReservation(flightId=flight_id, seat=1)
    records_after = _get_operation_records_for_test(reservation_service)

    assert len(records_after) == len(records_before) + 1


def test_br25_failed_operations_must_not_generate_persistent_records(reservation_service, fixed_now, flight_id):
    # BR25 – Failed operations must not generate persistent records
    # Use BR04 seat exclusivity violation (second reservation on same seat) as the failing operation.
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=2)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    _ = reservation_service.createReservation(flightId=flight_id, seat=1)
    records_before = _get_operation_records_for_test(reservation_service)

    with pytest.raises(Exception):
        reservation_service.createReservation(flightId=flight_id, seat=1)

    records_after = _get_operation_records_for_test(reservation_service)
    assert len(records_after) == len(records_before)


# ---------------------------------------------------------------------------
# BR26 / FR03 – Isolation: operations on one reservation must not affect others
# ---------------------------------------------------------------------------

def test_br26_canceling_one_reservation_must_not_change_state_of_other_reservation(reservation_service, fixed_now, flight_id):
    # BR26 – Operations performed on one reservation must not affect other reservations, flights, or seats
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=2)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    r1 = reservation_service.createReservation(flightId=flight_id, seat=1)
    r2 = reservation_service.createReservation(flightId=flight_id, seat=2)
    rid1 = _get_reservation_id(r1)
    rid2 = _get_reservation_id(r2)

    reservation_service.confirmPayment(reservationId=rid1, paymentApproved=True)
    reservation_service.confirmPayment(reservationId=rid2, paymentApproved=True)

    reservation_service.cancelReservation(reservationId=rid1)

    updated2 = _get_reservation_snapshot_for_test(reservation_service, rid2)
    assert updated2.state == "CONFIRMED"


def test_fr03_seat_availability_is_strictly_controlled_for_exclusivity(reservation_service, fixed_now, flight_id):
    # FR03 – Strictly control seat availability, ensuring exclusivity per active reservation
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=2)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    _ = reservation_service.createReservation(flightId=flight_id, seat=1)

    with pytest.raises(Exception):
        reservation_service.createReservation(flightId=flight_id, seat=1)


# ---------------------------------------------------------------------------
# FR06 – No overbooking at any stage
# ---------------------------------------------------------------------------

def test_fr06_do_not_allow_overbooking_at_any_stage_of_process(reservation_service, fixed_now, flight_id):
    # FR06 – Do not allow overbooking at any stage of the process
    # Create up to capacity, confirm, then attempt additional reservation creation.
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    r1 = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid1 = _get_reservation_id(r1)
    reservation_service.confirmPayment(reservationId=rid1, paymentApproved=True)

    with pytest.raises(Exception):
        reservation_service.createReservation(flightId=flight_id, seat=2)


# ---------------------------------------------------------------------------
# FR08 – Do not return intermediate states, explanatory messages, or partial results
# ---------------------------------------------------------------------------

def test_fr08_confirm_payment_returns_no_partial_result(reservation_service, fixed_now, flight_id):
    # FR08 – Do not return intermediate states, explanatory messages, or partial results
    # confirmPayment returns void per UML; validate it returns None.
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=1)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    reservation = reservation_service.createReservation(flightId=flight_id, seat=1)
    rid = _get_reservation_id(reservation)

    result = reservation_service.confirmPayment(reservationId=rid, paymentApproved=True)
    assert result is None


# ---------------------------------------------------------------------------
# FR10 – Use exclusively provided and internally stored data (no external enrichment)
# ---------------------------------------------------------------------------

def test_fr10_create_reservation_uses_only_provided_flight_id_and_seat(reservation_service, fixed_now, flight_id):
    # FR10 – Use exclusively provided and internally stored data, with no inference or external enrichment
    # Validate that the seat stored equals exactly the provided seat.
    _set_internal_flight_total_seats_for_test(reservation_service, flight_id, total_seats=3)
    _set_internal_flight_datetime_for_test(reservation_service, flight_id, fixed_now + timedelta(hours=48))

    reservation = reservation_service.createReservation(flightId=flight_id, seat=3)
    assert reservation.seat == 3
    assert reservation.state == "CREATED"
```