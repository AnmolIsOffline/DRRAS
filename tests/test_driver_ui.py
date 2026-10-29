from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_driver_dashboard_has_exactly_three_existing_workflow_shortcuts():
    app_js = (ROOT / 'static' / 'js' / 'app.js').read_text(encoding='utf-8')
    driver_module = app_js.split("    Driver: {", 1)[1].split("    Administrator: {", 1)[0]
    assert "title: 'Driver Operations Center'" in driver_module
    assert driver_module.count("['") == 3
    for title in ('My Dispatches', 'Current Trip & Route', 'Delivery Proof Center'):
        assert title in driver_module
    assert 'driver-operation-link' in app_js
    assert "'.role-action-card:not(.driver-operation-card)'" in app_js
    assert "currentPage = 'Vehicles & Dispatch'" in app_js
    assert 'showRouteModal(activeTrip.id)' in app_js
    assert 'openDeliveryProofModal(eligibleDispatch.id)' in app_js


def test_administrator_feature_hub_remains_separate_and_complete():
    app_js = (ROOT / 'static' / 'js' / 'app.js').read_text(encoding='utf-8')
    admin_module = app_js.split('    Administrator: {', 1)[1].split('\n    }\n  };', 1)[0]
    for title in ('User Access & Approvals', 'Urgency Engine Weights', 'Relief Master Data', 'Security & Audit Trail'):
        assert title in admin_module
    assert "session.role === 'Administrator'" in app_js


def test_driver_route_locations_use_saved_endpoints_without_fake_checkpoints():
    app_js = (ROOT / 'static' / 'js' / 'app.js').read_text(encoding='utf-8')
    driver_view = app_js.split('function renderDriverView(container)', 1)[1].split('// Plot only persisted', 1)[0]
    assert 'Recorded Dispatch Locations' in driver_view
    assert 'No Telemetry' in driver_view
    assert 'No route checkpoints are stored for this dispatch.' in driver_view
    assert 'activeTrip.warehouse_name' in driver_view
    assert 'activeTrip.destination' in driver_view
    assert 'Emergency Highway Bypass' not in driver_view


def test_delivery_proof_manifest_has_associated_labels_and_no_default_fieldset():
    app_js = (ROOT / 'static' / 'js' / 'app.js').read_text(encoding='utf-8')
    proof_modal = app_js.split('async function openDeliveryProofModal(dispatchId)', 1)[1].split('// 16.', 1)[0]
    assert 'proof-item-card' in proof_modal
    for field in ('Delivered', 'Returned', 'Damaged'):
        assert f'for="{field.lower()}-${{rowId}}"' in proof_modal
        assert f'id="{field.lower()}-${{rowId}}"' in proof_modal
    assert 'fieldset' not in proof_modal
    assert "querySelectorAll('[data-resource-id][data-loaded]')" in proof_modal
    assert 'quantity_delivered + i.quantity_returned + i.quantity_damaged !== i.loaded' in proof_modal


def test_driver_page_keeps_existing_map_dispatch_and_proof_authorization_workflows():
    app_js = (ROOT / 'static' / 'js' / 'app.js').read_text(encoding='utf-8')
    api = (ROOT / 'app.py').read_text(encoding='utf-8')
    routes = (ROOT / 'api_routes.py').read_text(encoding='utf-8')
    assert 'btn-driver-map-roads' in app_js and 'btn-driver-map-sat' in app_js
    assert 'function renderDispatchPage(container)' in app_js
    assert 'Export CSV' in app_js and 'dsp-route-btn' in app_js and 'dsp-proof-btn' in app_js
    assert "where=' WHERE d.driver_user_id=? AND d.owner_type=? AND d.owner_organization_id IS ?'" in api
    assert "if row['driver_user_id'] != user_id:" in routes
    assert "if dsp['status'] != 'Arrived':" in (ROOT / 'services.py').read_text(encoding='utf-8')


def test_driver_dashboard_has_database_backed_accept_and_reject_actions():
    app_js = (ROOT / 'static' / 'js' / 'app.js').read_text(encoding='utf-8')
    routes = (ROOT / 'api_routes.py').read_text(encoding='utf-8')
    services = (ROOT / 'services.py').read_text(encoding='utf-8')
    assert "fetch('/api/driver/assignments')" in app_js
    assert 'driver-assignment-accept' in app_js and 'driver-assignment-decline' in app_js
    assert "@api_bp.route('/api/driver/assignments/<int:assignment_id>/<action>'" in routes
    assert 'decide_driver_assignment_service' in routes
    assert 'DRIVER_ACCEPTANCE_PENDING' in services


def test_accepted_driver_assignment_keeps_route_map_and_navigation_action():
    app_js = (ROOT / 'static' / 'js' / 'app.js').read_text(encoding='utf-8')
    routes = (ROOT / 'api_routes.py').read_text(encoding='utf-8')
    no_trip_view = app_js.split('if (!activeTrip)', 1)[1].split('const isRerouted', 1)[0]
    assert "driverAssignments.find(a => a.driver_decision === 'Accepted')" in app_js
    assert 'Current Trip &amp; Route' in no_trip_view
    assert 'id="driver-real-map"' in no_trip_view
    assert 'driver-assignment-route-btn' in no_trip_view
    assert 'initDriverRealMap(acceptedAssignment)' in no_trip_view
    assert 'showRouteModal(acceptedAssignment)' in no_trip_view
    assert 'r.lat AS destination_lat,r.lng AS destination_lng' in routes
    assert 'wh.name AS warehouse_name,wh.lat AS pickup_lat,wh.lng AS pickup_lng' in routes
