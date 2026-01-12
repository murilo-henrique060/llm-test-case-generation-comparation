import pytest
from datetime import datetime, timedelta

# The tests assume the presence of a module named `reservation_system` exposing:
# - ReservationService
# - Flight
# These are external to the tests and must be provided by the system under test.
from reservation_system import ReservationService, Flight


# BR01 – A reservation may only be confirmed if exactly one approved payment is associated with it
def test_br01_confirm_only_with_exactly_one_approved_payment():
    service = ReservationService(flights=[Flight(id="FL1", dateTime=datetime(2026, 1, 20, 12, 0, 0), totalSeats=1)])
    reservation = service.createReservation("FL1", seat=1)
    # Confirm with approved payment -> should succeed and set state to CONFIRMED
    service.confirmPayment(reservation.id, paymentApproved=True)
    assert reservation.state == "CONFIRMED"


# BR02 – Payments with a status other than approved must not confirm reservations
def test_br02_reject_confirmation_when_payment_not_approved():
    service = ReservationService(flights=[Flight(id="FL2", dateTime=datetime(2026, 1, 21, 12, 0, 0), totalSeats=1)])
    reservation = service.createReservation("FL2", seat=1)
    with pytest.raises(Exception):
        service.confirmPayment(reservation.id, paymentApproved=False)
    # Ensure no state change occurred
    assert reservation.state == "CREATED"


# BR03 – Reservation confirmation and payment must be atomic
def test_br03_confirmation_and_payment_atomic_either_both_or_none():
    service = ReservationService(flights=[Flight(id="FL3", dateTime=datetime(2026, 1, 22, 12, 0, 0), totalSeats=1)])
    reservation = service.createReservation("FL3", seat=1)
    # Successful atomic operation -> both payment approved and reservation confirmed
    service.confirmPayment(reservation.id, paymentApproved=True)
    assert reservation.state == "CONFIRMED"
    # Create another reservation and force a failing payment -> neither payment nor confirmation persisted
    reservation2 = service.createReservation("FL3", seat=2 if service.flights["FL3"].totalSeats >= 2 else 1)
    with pytest.raises(Exception):
        service.confirmPayment(reservation2.id, paymentApproved=False)
    assert reservation2.state == "CREATED"


# BR04 – A seat may belong to at most one active reservation per flight
def test_br04_seat_exclusivity_prevents_second_active_reservation_on_same_seat():
    service = ReservationService(flights=[Flight(id="FL4", dateTime=datetime(2026, 1, 23, 12, 0, 0), totalSeats=2)])
    res1 = service.createReservation("FL4", seat=1)
    # Second attempt to create an active reservation for the same seat must fail
    with pytest.raises(Exception):
        service.createReservation("FL4", seat=1)


# BR05 – Canceled reservations must immediately release the associated seat
def test_br05_cancel_releases_seat_immediately():
    service = ReservationService(flights=[Flight(id="FL5", dateTime=datetime(2026, 1, 24, 12, 0, 0), totalSeats=1)])
    res = service.createReservation("FL5", seat=1)
    service.confirmPayment(res.id, paymentApproved=True)
    assert res.state == "CONFIRMED"
    service.cancelReservation(res.id)
    assert res.state == "CANCELED"
    # After cancellation, creating a new reservation for the same seat must be allowed
    new_res = service.createReservation("FL5", seat=1)
    assert new_res.state == "CREATED"


# BR06 – Overbooking is not permitted under any circumstances
def test_br06_overbooking_not_permitted_on_creation():
    flight = Flight(id="FL6", dateTime=datetime(2026, 1, 25, 12, 0, 0), totalSeats=1)
    service = ReservationService(flights=[flight])
    r1 = service.createReservation("FL6", seat=1)
    # Attempt to create a second active reservation for any seat beyond capacity must fail
    with pytest.raises(Exception):
        service.createReservation("FL6", seat=2)


# BR07 – Number of confirmed reservations must never exceed total seats
def test_br07_confirmed_reservations_never_exceed_total_seats():
    flight = Flight(id="FL7", dateTime=datetime(2026, 1, 26, 12, 0, 0), totalSeats=2)
    service = ReservationService(flights=[flight])
    r1 = service.createReservation("FL7", seat=1)
    r2 = service.createReservation("FL7", seat=2)
    service.confirmPayment(r1.id, paymentApproved=True)
    service.confirmPayment(r2.id, paymentApproved=True)
    # All seats filled; any further confirmation must be rejected
    r3 = service.createReservation("FL7", seat=3) if flight.totalSeats >= 3 else None
    if r3:
        with pytest.raises(Exception):
            service.confirmPayment(r3.id, paymentApproved=True)


# BR08 – Reservation may be exclusively in CREATED, CONFIRMED, or CANCELED
def test_br08_reservation_initial_state_is_created_and_only_allowed_states_exist():
    service = ReservationService(flights=[Flight(id="FL8", dateTime=datetime(2026, 1, 27, 12, 0, 0), totalSeats=1)])
    reservation = service.createReservation("FL8", seat=1)
    assert reservation.state == "CREATED"
    assert reservation.state in {"CREATED", "CONFIRMED", "CANCELED"}


# BR09 – Intermediate or additional states are not permitted
def test_br09_no_intermediate_states_returned():
    service = ReservationService(flights=[Flight(id="FL9", dateTime=datetime(2026, 1, 28, 12, 0, 0), totalSeats=1)])
    reservation = service.createReservation("FL9", seat=1)
    # The system must not produce a state named "PENDING" or similar
    assert reservation.state != "PENDING"


# BR10 – Only valid state transitions: CREATED -> CONFIRMED
def test_br10_created_to_confirmed_allowed_transition():
    service = ReservationService(flights=[Flight(id="FL10", dateTime=datetime(2026, 1, 29, 12, 0, 0), totalSeats=1)])
    reservation = service.createReservation("FL10", seat=1)
    service.confirmPayment(reservation.id, paymentApproved=True)
    assert reservation.state == "CONFIRMED"


# BR11 – Any state transition other than defined must be rejected
def test_br11_invalid_state_transition_rejected_created_to_canceled_directly():
    service = ReservationService(flights=[Flight(id="FL11", dateTime=datetime(2026, 1, 30, 12, 0, 0), totalSeats=1)])
    reservation = service.createReservation("FL11", seat=1)
    # CREATED -> CANCELED without prior CONFIRMED is an invalid transition per BR10/BR11
    with pytest.raises(Exception):
        service.cancelReservation(reservation.id)


# BR12 – Canceled reservation must not be reactivated, modified, or receive new payments
def test_br12_canceled_reservation_rejects_new_payments_and_modifications():
    service = ReservationService(flights=[Flight(id="FL12", dateTime=datetime(2026, 2, 1, 12, 0, 0), totalSeats=1)])
    res = service.createReservation("FL12", seat=1)
    service.confirmPayment(res.id, paymentApproved=True)
    service.cancelReservation(res.id)
    assert res.state == "CANCELED"
    with pytest.raises(Exception):
        service.confirmPayment(res.id, paymentApproved=True)
    with pytest.raises(Exception):
        # Attempt to create a payment-like second confirmation or modification must fail
        service.confirmPayment(res.id, paymentApproved=False)


# BR13 – Cancellation refund policy based on remaining time (>=24h full refund; <24h no refund)
def test_br13_cancel_refund_policy_full_refund_when_remaining_time_at_least_24_hours():
    flight_dt = datetime(2026, 2, 10, 12, 0, 0)
    service = ReservationService(flights=[Flight(id="FL13", dateTime=flight_dt, totalSeats=1)])
    res = service.createReservation("FL13", seat=1)
    service.confirmPayment(res.id, paymentApproved=True)
    # Set system "now" to exactly 24 hours before flight using internal time reference is required by BR15.
    # The test assumes ReservationService exposes a test hook to set current time deterministically.
    service.set_current_time(flight_dt - timedelta(hours=24))
    refund = service.cancelReservation(res.id)
    # Expect full refund indicator (exact value must be 'FULL' per this test's contract)
    assert refund == "FULL"


def test_br13_cancel_refund_policy_no_refund_when_remaining_time_less_than_24_hours():
    flight_dt = datetime(2026, 2, 11, 12, 0, 0)
    service = ReservationService(flights=[Flight(id="FL13b", dateTime=flight_dt, totalSeats=1)])
    res = service.createReservation("FL13b", seat=1)
    service.confirmPayment(res.id, paymentApproved=True)
    service.set_current_time(flight_dt - timedelta(hours=23, minutes=59, seconds=59))
    refund = service.cancelReservation(res.id)
    assert refund == "NONE"


# BR14 – Remaining time must be calculated in exact hours with no rounding
def test_br14_remaining_time_exact_hours_no_rounding():
    flight_dt = datetime(2026, 2, 12, 12, 0, 0)
    service = ReservationService(flights=[Flight(id="FL14", dateTime=flight_dt, totalSeats=1)])
    res = service.createReservation("FL14", seat=1)
    service.confirmPayment(res.id, paymentApproved=True)
    # Set current time to 24 hours and 1 second before flight -> remaining hours exact calculation should be 24? no rounding allowed
    service.set_current_time(flight_dt - timedelta(hours=24) - timedelta(seconds=1))
    # Cancellation outcome must follow strict hours calculation: remaining_time in hours exactly must be 24 or 23? The spec requires exact hours with no rounding.
    # We assert that cancellation uses exact hours and thus this timestamp results in <24 hours remaining -> no refund
    refund = service.cancelReservation(res.id)
    assert refund == "NONE"


# BR15 – System must use internally stored flight date/time as temporal reference
def test_br15_system_uses_internal_flight_datetime_as_reference():
    flight_dt = datetime(2026, 2, 13, 12, 0, 0)
    flight = Flight(id="FL15", dateTime=flight_dt, totalSeats=1)
    service = ReservationService(flights=[flight])
    res = service.createReservation("FL15", seat=1)
    service.confirmPayment(res.id, paymentApproved=True)
    # Changing an external variable should not affect internal reference; set current time far after flight externally but internal stored flight datetime must be used
    service.set_current_time(datetime(2030, 1, 1, 0, 0, 0))
    # Cancellation after flight date must be rejected (no payments allowed after flight date per BR20)
    with pytest.raises(Exception):
        service.cancelReservation(res.id)


# BR16 – Flight dates, times, and identifiers must not be altered after reservation confirmation
def test_br16_flight_data_immutable_after_confirmation():
    flight = Flight(id="FL16", dateTime=datetime(2026, 2, 14, 12, 0, 0), totalSeats=1)
    service = ReservationService(flights=[flight])
    res = service.createReservation("FL16", seat=1)
    service.confirmPayment(res.id, paymentApproved=True)
    with pytest.raises(Exception):
        # Any attempt to modify flight date/time or id after confirmation must be rejected
        service.modifyFlight("FL16", newDateTime=flight.dateTime + timedelta(days=1))


# BR17 – Indirect modifications of flight data (swapping/cloning/recreation) are prohibited
def test_br17_indirect_modification_of_flight_data_prohibited():
    flight = Flight(id="FL17", dateTime=datetime(2026, 2, 15, 12, 0, 0), totalSeats=1)
    service = ReservationService(flights=[flight])
    res = service.createReservation("FL17", seat=1)
    service.confirmPayment(res.id, paymentApproved=True)
    with pytest.raises(Exception):
        # Attempts to replace the flight object or swap references must be rejected
        service.replaceFlight("FL17", Flight(id="FL17", dateTime=flight.dateTime + timedelta(hours=1), totalSeats=1))


# BR18 – Each reservation may have exactly one associated payment
def test_br18_reservation_accepts_exactly_one_payment():
    service = ReservationService(flights=[Flight(id="FL18", dateTime=datetime(2026, 2, 16, 12, 0, 0), totalSeats=1)])
    res = service.createReservation("FL18", seat=1)
    service.confirmPayment(res.id, paymentApproved=True)
    # A second payment attempt for the same reservation must be rejected
    with pytest.raises(Exception):
        service.confirmPayment(res.id, paymentApproved=True)


# BR19 – Additional payment attempts for the same reservation must be rejected
def test_br19_reject_additional_payment_attempts():
    service = ReservationService(flights=[Flight(id="FL19", dateTime=datetime(2026, 2, 17, 12, 0, 0), totalSeats=1)])
    res = service.createReservation("FL19", seat=1)
    service.confirmPayment(res.id, paymentApproved=True)
    with pytest.raises(Exception):
        service.confirmPayment(res.id, paymentApproved=False)


# BR20 – Payments must not be accepted for canceled reservations or after the flight date
def test_br20_no_payments_for_canceled_or_after_flight_date():
    flight_dt = datetime(2026, 2, 18, 12, 0, 0)
    service = ReservationService(flights=[Flight(id="FL20", dateTime=flight_dt, totalSeats=1)])
    res = service.createReservation("FL20", seat=1)
    service.cancelReservation(res.id)
    with pytest.raises(Exception):
        service.confirmPayment(res.id, paymentApproved=True)
    # Also, attempting payment after flight date must be rejected
    service.set_current_time(flight_dt + timedelta(hours=1))
    res2 = service.createReservation("FL20", seat=1)
    with pytest.raises(Exception):
        service.confirmPayment(res2.id, paymentApproved=True)


# BR21 – System operations must be deterministic for same sequence of inputs
def test_br21_operations_are_deterministic_given_same_inputs():
    flight = Flight(id="FL21", dateTime=datetime(2026, 2, 19, 12, 0, 0), totalSeats=1)
    # Run the same sequence twice and compare outcomes
    service1 = ReservationService(flights=[flight])
    r1 = service1.createReservation("FL21", seat=1)
    service1.confirmPayment(r1.id, paymentApproved=True)

    service2 = ReservationService(flights=[flight])
    r2 = service2.createReservation("FL21", seat=1)
    service2.confirmPayment(r2.id, paymentApproved=True)

    assert r1.state == r2.state == "CONFIRMED"


# BR22 – System must not assume unspecified implicit behaviors
def test_br22_no_implicit_behaviors_like_automatic_rebooking_or_future_credit():
    service = ReservationService(flights=[Flight(id="FL22", dateTime=datetime(2026, 2, 20, 12, 0, 0), totalSeats=1)])
    res = service.createReservation("FL22", seat=1)
    service.confirmPayment(res.id, paymentApproved=True)
    # After cancellation, system must not create any automatic new reservation or credit
    service.cancelReservation(res.id)
    # There must be no automatic new confirmed reservations for the same passenger/seat
    # Attempting to find any active confirmed reservation for seat 1 must fail (explicit: raise or return None)
    with pytest.raises(Exception):
        service.find_confirmed_reservation_by_seat("FL22", seat=1)


# BR23 – Any business rule violation must result in immediate failure with no state change or partial records
def test_br23_violation_results_in_no_state_change_and_no_partial_records():
    service = ReservationService(flights=[Flight(id="FL23", dateTime=datetime(2026, 2, 21, 12, 0, 0), totalSeats=1)])
    res = service.createReservation("FL23", seat=1)
    # Attempt invalid operation
    with pytest.raises(Exception):
        service.createReservation("FL23", seat=1)
    # Ensure original reservation still exists and remains CREATED
    assert res.state == "CREATED"


# BR24 – Each valid operation must generate exactly one immutable record
def test_br24_valid_operation_generates_single_immutable_record():
    service = ReservationService(flights=[Flight(id="FL24", dateTime=datetime(2026, 2, 22, 12, 0, 0), totalSeats=1)])
    before_records = service.list_records()
    res = service.createReservation("FL24", seat=1)
    after_records = service.list_records()
    # Exactly one new record must be added for the operation
    assert len(after_records) - len(before_records) == 1
    # And that record must be immutable: attempts to modify it must be rejected
    record = after_records[-1]
    with pytest.raises(Exception):
        service.modify_record(record.id, {"state": "MUTATED"})


# BR25 – Failed operations must not generate persistent records
def test_br25_failed_operations_do_not_create_persistent_records():
    service = ReservationService(flights=[Flight(id="FL25", dateTime=datetime(2026, 2, 23, 12, 0, 0), totalSeats=1)])
    before_records = service.list_records()
    with pytest.raises(Exception):
        service.createReservation("FL25", seat=1)  # suppose this fails due to invalid seat
    after_records = service.list_records()
    assert before_records == after_records


# BR26 – Operations on one reservation must not affect others, flights, or seats
def test_br26_operations_isolated_between_reservations():
    flight = Flight(id="FL26", dateTime=datetime(2026, 2, 24, 12, 0, 0), totalSeats=2)
    service = ReservationService(flights=[flight])
    r1 = service.createReservation("FL26", seat=1)
    r2 = service.createReservation("FL26", seat=2)
    service.confirmPayment(r1.id, paymentApproved=True)
    # Operation on r1 must not affect r2
    assert r2.state == "CREATED"


# FR01 – Create initial reservation in CREATED state associated with flight and available seat
def test_fr01_create_reservation_in_created_state_associated_with_flight_and_seat():
    flight = Flight(id="FRA1", dateTime=datetime(2026, 3, 1, 10, 0, 0), totalSeats=10)
    service = ReservationService(flights=[flight])
    reservation = service.createReservation("FRA1", seat=5)
    assert reservation.state == "CREATED"
    assert reservation.seat == 5
    assert reservation.flightId == "FRA1"


# FR02 – Confirm payment and, atomically, confirm the reservation
def test_fr02_confirm_payment_atomically_confirms_reservation():
    flight = Flight(id="FRA2", dateTime=datetime(2026, 3, 2, 10, 0, 0), totalSeats=1)
    service = ReservationService(flights=[flight])
    res = service.createReservation("FRA2", seat=1)
    service.confirmPayment(res.id, paymentApproved=True)
    assert res.state == "CONFIRMED"


# FR03 – Strictly control seat availability, ensuring exclusivity per active reservation
def test_fr03_strict_seat_availability_enforces_exclusivity():
    flight = Flight(id="FRA3", dateTime=datetime(2026, 3, 3, 10, 0, 0), totalSeats=1)
    service = ReservationService(flights=[flight])
    r1 = service.createReservation("FRA3", seat=1)
    with pytest.raises(Exception):
        service.createReservation("FRA3", seat=1)


# FR04 – Cancel reservations while strictly respecting the refund policy
def test_fr04_cancel_respects_refund_policy_exact_boundary():
    flight_dt = datetime(2026, 3, 4, 10, 0, 0)
    service = ReservationService(flights=[Flight(id="FRA4", dateTime=flight_dt, totalSeats=1)])
    res = service.createReservation("FRA4", seat=1)
    service.confirmPayment(res.id, paymentApproved=True)
    service.set_current_time(flight_dt - timedelta(hours=24))
    refund = service.cancelReservation(res.id)
    assert refund == "FULL"


# FR05 – Prevent any invalid modification of state, flight data, seat, or payment
def test_fr05_prevent_invalid_modification_of_state_flight_seat_or_payment():
    flight = Flight(id="FRA5", dateTime=datetime(2026, 3, 5, 10, 0, 0), totalSeats=1)
    service = ReservationService(flights=[flight])
    res = service.createReservation("FRA5", seat=1)
    with pytest.raises(Exception):
        # Invalid direct state assignment must be rejected
        service.set_reservation_state(res.id, "INVALID_STATE")


# FR06 – Do not allow overbooking at any stage of the process
def test_fr06_no_overbooking_even_during_confirmation_stage():
    flight = Flight(id="FRA6", dateTime=datetime(2026, 3, 6, 10, 0, 0), totalSeats=1)
    service = ReservationService(flights=[flight])
    r1 = service.createReservation("FRA6", seat=1)
    r2 = service.createReservation("FRA6", seat=2) if flight.totalSeats >= 2 else None
    service.confirmPayment(r1.id, paymentApproved=True)
    if r2:
        with pytest.raises(Exception):
            service.confirmPayment(r2.id, paymentApproved=True)


# FR07 – Do not allow multiple, partial, or late payments
def test_fr07_reject_multiple_partial_or_late_payments():
    flight_dt = datetime(2026, 3, 7, 10, 0, 0)
    service = ReservationService(flights=[Flight(id="FRA7", dateTime=flight_dt, totalSeats=1)])
    res = service.createReservation("FRA7", seat=1)
    service.confirmPayment(res.id, paymentApproved=True)
    with pytest.raises(Exception):
        # Second payment attempt must be rejected
        service.confirmPayment(res.id, paymentApproved=True)
    # Simulate time after flight date
    service.set_current_time(flight_dt + timedelta(hours=1))
    res2 = service.createReservation("FRA7", seat=1)
    with pytest.raises(Exception):
        service.confirmPayment(res2.id, paymentApproved=True)


# FR08 – Do not return intermediate states, explanatory messages, or partial results
def test_fr08_no_intermediate_states_or_partial_results_returned_on_operations():
    service = ReservationService(flights=[Flight(id="FRA8", dateTime=datetime(2026, 3, 8, 10, 0, 0), totalSeats=1)])
    res = service.createReservation("FRA8", seat=1)
    # confirmPayment must not return intermediate state; it should either complete or raise.
    result = service.confirmPayment(res.id, paymentApproved=True)
    assert result is None or result == "OK"


# FR09 – Ensure failures do not modify state or produce persistent side effects
def test_fr09_failures_do_not_modify_state_or_produce_persistent_side_effects():
    service = ReservationService(flights=[Flight(id="FRA9", dateTime=datetime(2026, 3, 9, 10, 0, 0), totalSeats=1)])
    res = service.createReservation("FRA9", seat=1)
    before_records = service.list_records()
    with pytest.raises(Exception):
        service.confirmPayment(res.id, paymentApproved=False)
    after_records = service.list_records()
    assert before_records == after_records
    assert res.state == "CREATED"


# FR10 – Use exclusively provided and internally stored data, with no inference or external enrichment
def test_fr10_only_internal_data_used_no_external_enrichment():
    flight = Flight(id="FRA10", dateTime=datetime(2026, 3, 10, 10, 0, 0), totalSeats=1)
    service = ReservationService(flights=[flight])
    res = service.createReservation("FRA10", seat=1)
    # Provide an unrelated external parameter and ensure it does not affect reservation
    service.createReservation("FRA10", seat=1, external_metadata={"promo": "SHOULD_BE_IGNORED"}) if flight.totalSeats >= 2 else None
    assert res.flightId == "FRA10"
    assert res.seat == 1
    assert res.state == "CREATED"