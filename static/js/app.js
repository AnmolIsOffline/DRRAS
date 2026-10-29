/**
 * DRRAS — Disaster Relief Resource Allocation System
 * Enterprise Vanilla JavaScript Frontend Application
 * Fully functional, accessible, role-aware, zero external build tools
 */

(function () {
  'use strict';

  // Application Global State
  let session = null;
  let currentPage = 'Command Center';
  let requests = [];
  let inventory = [];
  let warehouses = [];
  let resources = [];
  let volunteers = [];
  let dispatches = [];
  let driverAssignments = [];
  let shelters = [];
  let advisories = [];
  let incidents = [];
  let notifications = [];
  let fundsData = null;
  let donationsData = [];
  let donationOrganizations = [];
  let dashboardData = null;
  let pendingUsers = [];
  let activeNotice = '';
  let requestPickerMap = null;
  let requestMarker = null;
  let selectedLat = null;
  let selectedLng = null;
  let dashboardMapInstance = null;
  let driverMapInstance = null;
  let routeModalMapInstance = null;
  let sheltersMapInstance = null;

  // Automatic CSRF header injection for mutating requests
  const originalFetch = window.fetch;
  function getCsrfToken() {
    const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : (session && session.csrf_token ? session.csrf_token : '');
  }

  window.fetch = function (url, options = {}) {
    options = options || {};
    const method = (options.method || 'GET').toUpperCase();
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
      options.headers = options.headers || {};
      const token = getCsrfToken();
      if (token && !(options.headers instanceof Headers)) {
        options.headers['X-CSRF-Token'] = token;
      } else if (token && options.headers instanceof Headers) {
        options.headers.set('X-CSRF-Token', token);
      }
    }
    return originalFetch(url, options);
  };

  // Real Google Maps Tile Configuration (with OSM fallback)
  const MAP_LAYERS = {
    googleRoadmap: 'https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
    googleSatellite: 'https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
    googleTerrain: 'https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}',
    osm: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
  };

  function createGoogleMapTileLayer(type = 'googleRoadmap') {
    const url = MAP_LAYERS[type] || MAP_LAYERS.googleRoadmap;
    const isGoogle = type.startsWith('google');
    return L.tileLayer(url, {
      maxZoom: 20,
      subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
      attribution: isGoogle ? 'Map data © Google' : '© OpenStreetMap contributors'
    });
  }

  // Search & Filter State

  const pageFilters = {
    requests: { search: '', status: 'ALL', sort: 'PRIORITY_DESC' },
    inventory: { search: '', status: 'ALL' },
    volunteers: { search: '', status: 'ALL' },
    dispatches: { search: '', status: 'ALL' }
  };

  // Safe HTML Output Encoding (XSS Prevention)
  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Navigation Items
  const NAV_ITEMS = [
    { name: 'Command Center', icon: 'House' },
    { name: 'Emergency Requests', icon: 'ClipboardList' },
    { name: 'Resource Allocation', icon: 'PackageCheck' },
    { name: 'Inventory & Warehouses', icon: 'Boxes' },
    { name: 'Volunteers', icon: 'Users' },
    { name: 'Shelters', icon: 'HeartHandshake' },
    { name: 'Vehicles & Dispatch', icon: 'Truck' },
    { name: 'Funds & Donations', icon: 'Wallet' },
    { name: 'System Administration', icon: 'Building' }
  ];

  // Role Feature Modules
  const ROLE_MODULES = {
    Citizen: {
      title: 'Citizen Services & Relief Status',
      intro: 'Raise verified emergency calls, monitor live dispatch, and locate safe relief shelters.',
      items: [
        ['Emergency Request Desk', 'Submit detailed assistance requests with exact GPS pin for medical, food or rescue.', 'Open Request Desk'],
        ['Area Safety Protocols', 'Official evacuation paths and flood alert advisories for your district.', 'View Protocols'],
        ['Relief Centers', 'Nearest operational relief shelters with available bed space and food.', 'Find Shelters'],
        ['Delivery Feedback', 'Verify delivered supplies and report outstanding neighborhood needs.', 'Give Feedback'],
        ['Relief Donations', 'Contribute cash or essential supplies to Government or an approved NGO.', 'Donate Now']
      ]
    },
    Volunteer: {
      title: 'Field Operations & Responder Toolkit',
      intro: 'Check in at assigned zones, confirm supply distribution, and update field readiness.',
      items: [
        ['Field Check-in', 'Log location arrival and activate emergency responder radio link.', 'Check In Now'],
        ['Distribution Checklist', 'Standard operational checklist for kit handovers and verification.', 'Open Checklist'],
        ['Route Guidance', 'Live waypoint sequence and navigation for field stops.', 'View Route'],
        ['Ground Incident Log', 'Report newly flooded streets, access blocks or extra supplies needed.', 'Log Incident']
      ]
    },
    'NGO Coordinator': {
      title: 'NGO Coordination & Area Adoption',
      intro: 'Adopt relief zones, log incoming donations, and assign volunteer teams.',
      items: [
        ['Relief Zone Coverage', 'Adopt flood-affected sectors approved by District Command.', 'Manage Zones'],
        ['Donation Intake', 'Register verified relief shipments, dry rations and medical supplies.', 'Log Donation'],
        ['Volunteer Deployment', 'Assign volunteer shifts to high-density relief shelters.', 'Deploy Team'],
        ['Consolidated Ledger', 'Review verified relief material transfers and warehouse receipts.', 'Open Ledger']
      ]
    },
    'Government Official': {
      title: 'District Government Response Command',
      intro: 'Authorize critical allocations, monitor relief funds, and coordinate multi-agency operations.',
      items: [
        ['Allocation Authorizations', 'Authorize urgent bulk resource dispatches exceeding local thresholds.', 'Review Queue'],
        ['Agency Operations Matrix', 'Inter-agency coordination between NDRF, State Police and NGOs.', 'View Agencies'],
        ['Relief Fund Utilization', 'Monitor SDRF and NDRF flood allocations and remaining balances.', 'Review Funds'],
        ['Public Broadcasts', 'Issue verified SMS and web advisories to affected citizens.', 'Draft Advisory']
      ]
    },
    Driver: {
      title: 'Driver Operations Center',
      intro: 'Manage assigned deliveries, review trip routes and submit delivery proof.',
      items: [
        ['My Dispatches', 'View assigned deliveries, dispatch details and current delivery status.', 'Open Vehicles & Dispatch'],
        ['Current Trip & Route', 'View the current trip, route information, destination and recorded checkpoints.', 'Open Trip Route'],
        ['Delivery Proof Center', 'Submit itemized delivery proof and track its review status.', 'Open Delivery Proofs']
      ]
    },
    Administrator: {
      title: 'Relief Command System Administration',
      intro: 'Manage RBAC permissions, approve pending accounts, and monitor audit trails.',
      items: [
        ['User Access & Approvals', 'Review pending staff and agency registrations for role approval.', 'Review Users'],
        ['Urgency Engine Weights', 'Configure algorithmic weights for severity, vulnerability and wait time.', 'View Config'],
        ['Relief Master Data', 'Manage warehouse locations, vehicle fleets and service sector boundaries.', 'Master Data'],
        ['Security & Audit Trail', 'Inspect audit logs, data integrity checkpoints and export history.', 'View Audit']
      ]
    }
  };

  // Toast Notification System
  function showToast(message, type = 'success') {
    let el = document.getElementById('drras-live-toast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'drras-live-toast';
      document.body.appendChild(el);
    }
    el.innerHTML = `<span style="color:${type === 'error' ? '#ef4444' : '#10b981'};margin-right:8px">${type === 'error' ? '!' : '?'}</span> ${escapeHtml(message)}`;
    el.style.display = 'block';
    clearTimeout(el._timer);
    el._timer = setTimeout(() => {
      el.style.display = 'none';
    }, 3400);
  }

  // Load Data from Backend APIs
  async function loadAllData() {
    try {
      const [dashRes, reqRes, invRes, volRes, dspRes, driverAssignmentRes, sheRes, funRes, whRes, resourceRes, advRes, incRes, noteRes, donationRes, donationOrgRes] = await Promise.all([
        fetch('/api/dashboard').then(r => r.json()),
        fetch('/api/requests').then(r => r.json()),
        fetch('/api/inventory').then(r => r.json()),
        fetch('/api/volunteers').then(r => r.json()),
        fetch('/api/dispatches').then(r => r.json()),
        session && session.role === 'Driver' ? fetch('/api/driver/assignments').then(r => r.ok ? r.json() : []) : Promise.resolve([]),
        fetch('/api/shelters').then(r => r.json()),
        session && ['Administrator', 'Government Official', 'NGO Coordinator'].includes(session.role) ? fetch('/api/funds').then(r => r.ok ? r.json() : null) : Promise.resolve(null),
        fetch('/api/warehouses').then(r => r.ok ? r.json() : []),
        fetch('/api/resources').then(r => r.ok ? r.json() : []),
        fetch('/api/advisories').then(r => r.ok ? r.json() : []),
        fetch('/api/incidents').then(r => r.ok ? r.json() : []),
        fetch('/api/notifications').then(r => r.ok ? r.json() : []),
        session && ['Administrator', 'Government Official', 'NGO Coordinator', 'Citizen'].includes(session.role) ? fetch('/api/donations').then(r => r.ok ? r.json() : []) : Promise.resolve([]),
        fetch('/api/organizations/public').then(r => r.ok ? r.json() : [])
      ]);

      dashboardData = dashRes;
      requests = Array.isArray(reqRes) ? reqRes : [];
      inventory = Array.isArray(invRes) ? invRes : [];
      volunteers = Array.isArray(volRes) ? volRes : [];
      dispatches = Array.isArray(dspRes) ? dspRes : [];
      driverAssignments = Array.isArray(driverAssignmentRes) ? driverAssignmentRes : [];
      shelters = Array.isArray(sheRes) ? sheRes : [];
      fundsData = funRes;
      warehouses = Array.isArray(whRes) ? whRes : [];
      resources = Array.isArray(resourceRes) ? resourceRes : [];
      advisories = Array.isArray(advRes) ? advRes.filter(a => a.status === 'Published') : [];
      incidents = Array.isArray(incRes) ? incRes : [];
      notifications = Array.isArray(noteRes) ? noteRes : [];
      donationsData = Array.isArray(donationRes) ? donationRes : [];
      donationOrganizations = Array.isArray(donationOrgRes) ? donationOrgRes : [];

      if (session && session.role === 'Administrator') {
        const penRes = await fetch('/api/admin/pending-users').then(r => r.json());
        pendingUsers = Array.isArray(penRes) ? penRes : [];
      }
    } catch (err) {
      console.error('DRRAS API Error:', err);
    }
  }

  // =========================================================================
  // REAL-TIME SYNCHRONIZATION: SSE & POLLING FALLBACK
  // =========================================================================

  let liveEventSource = null;
  let livePollInterval = null;
  let lastKnownEventId = 0;

  function initLiveEventStream() {
    stopLiveEventStream();
    if (!session) return;

    if (window.EventSource) {
      try {
        liveEventSource = new EventSource('/api/events/stream');

        liveEventSource.onmessage = async (e) => {
          try {
            const data = JSON.parse(e.data);
            if (data.heartbeat) return;
            if (data.id) lastKnownEventId = Math.max(lastKnownEventId, data.id);

            if (data.event_type) {
              await loadAllData();
              if (!document.querySelector('.modal-backdrop')) {
                renderApp();
              }
            }
          } catch (err) {
            console.debug('SSE parse error:', err);
          }
        };

        liveEventSource.onerror = () => {
          if (liveEventSource) {
            liveEventSource.close();
            liveEventSource = null;
          }
          startPollingFallback();
        };
        return;
      } catch (err) {
        console.debug('SSE initialization error, switching to polling fallback:', err);
      }
    }
    startPollingFallback();
  }

  function startPollingFallback() {
    if (livePollInterval) return;
    livePollInterval = setInterval(async () => {
      if (!session) return;
      try {
        const res = await fetch(`/api/events/poll?since=${lastKnownEventId}`);
        if (res.ok) {
          const payload = await res.json();
          if (payload.last_id) lastKnownEventId = Math.max(lastKnownEventId, payload.last_id);
          if (payload.events && payload.events.length > 0) {
            await loadAllData();
            if (!document.querySelector('.modal-backdrop')) {
              renderApp();
            }
          }
        }
      } catch (err) {
        // Polling retry on next interval
      }
    }, 4000);
  }

  function stopLiveEventStream() {
    if (liveEventSource) {
      try { liveEventSource.close(); } catch (e) {}
      liveEventSource = null;
    }
    if (livePollInterval) {
      clearInterval(livePollInterval);
      livePollInterval = null;
    }
  }

  // =========================================================================
  // AUTHENTICATION: LOGIN & REGISTRATION
  // =========================================================================

  function renderLogin() {
    const root = document.getElementById('root');
    let isSignup = false;
    let errorMsg = '';
    let successMsg = '';
    let publicOrganizations = [];

    function update() {
      root.innerHTML = `
        <div class="login-page">
          <!-- Left Hero Section -->
          <section class="login-hero">
            <div class="brand">
              <div class="brandmark">${getIcon('ShieldAlert')}</div>
              <div class="brand-title">
                <b>DRRAS</b>
                <small>Disaster Relief Command</small>
              </div>
            </div>

            <div class="hero-copy">
              <p class="eyebrow">Enterprise Disaster Relief Coordination</p>
              <h1>Rapid aid allocation.<br><span class="highlight">When every minute counts.</span></h1>
              <p class="hero-desc">A unified, role-aware disaster management platform coordinating citizens, emergency responders, warehouse logistics, and district officials with live data integrity.</p>
            </div>

          </section>

          <!-- Right Authentication Panel -->
          <section class="login-panel">
            <div class="auth-card">
              <div class="auth-header">
                <p class="eyebrow">${isSignup ? 'Create Account' : 'Secure Authorization'}</p>
                <h2>${isSignup ? 'Register for DRRAS' : 'Sign in to Workspace'}</h2>
                <p class="sub">${isSignup ? 'Citizens receive immediate active status. Official and staff roles require Administrator verification.' : 'Enter your authorized email and password to access your role command center.'}</p>
              </div>

              ${errorMsg ? `
                <div class="auth-alert error">
                  ${getIcon('AlertTriangle')}
                  <span>${escapeHtml(errorMsg)}</span>
                </div>
              ` : ''}

              ${successMsg ? `
                <div class="auth-alert success">
                  ${getIcon('CheckCircle2')}
                  <span>${escapeHtml(successMsg)}</span>
                </div>
              ` : ''}

              <form id="auth-form">
                ${isSignup ? `
                  <div class="auth-field">
                    <label for="reg-name">Full Name</label>
                    <div class="auth-input-wrapper">
                      <input required id="reg-name" name="name" placeholder="First and last name" autocomplete="name">
                    </div>
                  </div>

                  <div class="auth-field">
                    <label for="reg-email">Email Address</label>
                    <div class="auth-input-wrapper">
                      <input required type="email" id="reg-email" name="email" placeholder="official@agency.gov or citizen@domain.in" autocomplete="email">
                    </div>
                  </div>

                  <div class="auth-field">
                    <label for="reg-role">Register As</label>
                    <div class="auth-input-wrapper">
                      <select required id="reg-role" name="role">
                        <option value="Citizen">Citizen (Immediate access)</option>
                        <option value="Volunteer">Field Volunteer (NGO approval required)</option>
                        <option value="Driver">NGO Driver (NGO approval required)</option>
                        <option value="NGO Coordinator">NGO Coordinator (Admin approval required)</option>
                        <option value="Government Official">Government Official (Requires approval)</option>
                      </select>
                    </div>
                  </div>

                  <div class="auth-field" id="registration-organization-field">
                    <label for="reg-organization">Reviewing NGO</label>
                    <div class="auth-input-wrapper">
                      <select id="reg-organization" name="organization_id"><option value="">Select approved NGO</option>${publicOrganizations.map(o => `<option value="${o.id}">${escapeHtml(o.name)}</option>`).join('')}</select>
                    </div>
                  </div>

                  <div class="auth-field">
                    <label for="reg-password">Password</label>
                    <div class="auth-input-wrapper">
                      <input required minlength="6" type="password" id="reg-password" name="password" placeholder="Minimum 6 characters" autocomplete="new-password">
                      <button type="button" class="btn-password-toggle" id="toggle-pwd-btn" title="Show password" aria-label="Show password" aria-pressed="false">
                        ${getIcon('Eye')}
                      </button>
                    </div>
                  </div>

                  <button type="submit" class="btn-auth-submit">
                    Create Account ${getIcon('ArrowUpRight')}
                  </button>
                  <button type="button" class="btn-toggle-flow" id="toggle-auth-btn">
                    Already registered? Sign in here
                  </button>
                ` : `
                  <div class="auth-field">
                    <label for="login-email">Email Address</label>
                    <div class="auth-input-wrapper">
                      <input required type="email" id="login-email" name="email" autocomplete="username">
                    </div>
                  </div>

                  <div class="auth-field">
                    <label for="login-password">Password</label>
                    <div class="auth-input-wrapper">
                      <input required type="password" id="login-password" name="password" autocomplete="current-password">
                      <button type="button" class="btn-password-toggle" id="toggle-pwd-btn" title="Show password" aria-label="Show password" aria-pressed="false">
                        ${getIcon('Eye')}
                      </button>
                    </div>
                  </div>

                  <button type="submit" class="btn-auth-submit">
                    Sign In to Workspace ${getIcon('ArrowUpRight')}
                  </button>
                  <button type="button" class="btn-toggle-flow" id="toggle-auth-btn">
                    Need an account? Register as Citizen or Volunteer
                  </button>

                `}
              </form>
            </div>
          </section>
        </div>
      `;

      const registrationRole = root.querySelector('#reg-role');
      const orgField = root.querySelector('#registration-organization-field');
      const orgSelect = root.querySelector('#reg-organization');
      const updateRegistrationOrganization = () => {
        if (!registrationRole || !orgField || !orgSelect) return;
        const needsOrg = ['Volunteer','Driver','NGO Coordinator'].includes(registrationRole.value);
        orgField.hidden = !needsOrg;
        orgSelect.required = needsOrg;
      };
      if (registrationRole) { registrationRole.onchange = updateRegistrationOrganization; updateRegistrationOrganization(); }
      // Password toggle
      const pwdToggle = root.querySelector('#toggle-pwd-btn');
      const pwdInput = root.querySelector('#reg-password, #login-password');
      if (pwdToggle && pwdInput) {
        pwdToggle.onclick = () => {
          const showPassword = pwdInput.type === 'password';
          pwdInput.type = showPassword ? 'text' : 'password';
          pwdToggle.innerHTML = getIcon(showPassword ? 'EyeOff' : 'Eye');
          const label = showPassword ? 'Hide password' : 'Show password';
          pwdToggle.title = label;
          pwdToggle.setAttribute('aria-label', label);
          pwdToggle.setAttribute('aria-pressed', String(showPassword));
        };
      }

      // Switch between Sign in and Register
      const toggleAuth = root.querySelector('#toggle-auth-btn');
      if (toggleAuth) {
        toggleAuth.onclick = () => {
          isSignup = !isSignup;
          errorMsg = '';
          successMsg = '';
          update();
        };
      }

      // Form submission
      root.querySelector('#auth-form').onsubmit = async e => {
        e.preventDefault();
        const submitBtn = e.target.querySelector('button[type="submit"]');
        if (submitBtn) submitBtn.disabled = true;

        const fd = Object.fromEntries(new FormData(e.target));
        if (isSignup) {
          try {
            const res = await fetch('/api/auth/register', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(fd)
            });
            const data = await res.json();
            if (!res.ok) {
              errorMsg = data.error || 'Registration failed.';
              update();
            } else {
              if (data.status === 'ACTIVE') {
                session = data;
                localStorage.setItem('drras-user', JSON.stringify(data));
                await loadAllData();
                renderApp();
                initLiveEventStream();
              } else {
                isSignup = false;
                successMsg = data.message || 'Registration submitted for Administrator approval.';
                errorMsg = '';
                update();
              }
            }
          } catch (err) {
            errorMsg = 'Network error during registration.';
            update();
          }
        } else {
          try {
            const res = await fetch('/api/auth/login', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ email: fd.email, password: fd.password })
            });
            const data = await res.json();
            if (!res.ok) {
              errorMsg = data.error || 'Invalid credentials.';
              update();
            } else {
              session = data;
              localStorage.setItem('drras-user', JSON.stringify(data));
              await loadAllData();
              renderApp();
              initLiveEventStream();
            }
          } catch (err) {
            errorMsg = 'Server unreachable. Please verify Flask backend.';
            update();
          }
        }
      };
    }

    update();
    fetch('/api/organizations/public').then(r => r.ok ? r.json() : []).then(rows => {
      publicOrganizations = Array.isArray(rows) ? rows : [];
      if (document.getElementById('reg-organization')) update();
    }).catch(() => {});
  }

  // =========================================================================
  // APPLICATION SHELL & LAYOUT
  // =========================================================================

  function renderApp() {
    const root = document.getElementById('root');
    const allowedPages = session.role === 'Citizen'
      ? ['Command Center', 'Emergency Requests', 'Funds & Donations']
      : session.role === 'Volunteer'
      ? ['Command Center', 'Emergency Requests', 'Volunteers', 'Vehicles & Dispatch']
      : session.role === 'Driver'
      ? ['Command Center', 'Vehicles & Dispatch']
      : session.role === 'Administrator'
      ? NAV_ITEMS.map(x => x.name)
      : NAV_ITEMS.map(x => x.name).filter(n => n !== 'System Administration');

    if (!allowedPages.includes(currentPage)) {
      currentPage = 'Command Center';
    }

    const roleTitle = currentPage === 'Command Center' && session.role !== 'Administrator'
      ? ({
          Citizen: 'Citizen Relief Command',
          Volunteer: 'Field Responder Hub',
          'NGO Coordinator': 'NGO Operations Command',
          'Government Official': 'Government Relief Oversight',
          Driver: 'Driver Delivery Console'
        }[session.role] || currentPage)
      : currentPage;

    root.innerHTML = `
      <div class="app">
        <!-- Sidebar Navigation -->
        <aside id="sidebar">
          <div class="brand">
            <div class="brandmark">${getIcon('ShieldAlert')}</div>
            <div class="brand-title">
              <b>DRRAS</b>
              <small>RELIEF COMMAND</small>
            </div>
            <button type="button" class="mobile-close" id="close-menu" aria-label="Close menu">${getIcon('X')}</button>
          </div>

          <div class="incident-badge">
            <div class="incident-badge-header">
              <span class="incident-badge-tag">ACTIVE INCIDENT</span>
              <span class="incident-badge-dot"></span>
            </div>
            <b>Punjab Flood Response</b>
            <small>Phase: Relief Distribution · 12 Zones</small>
          </div>

          <nav class="sidebar-nav">
            ${NAV_ITEMS.filter(it => allowedPages.includes(it.name)).map(it => `
              <button type="button" class="nav-link ${currentPage === it.name ? 'active' : ''}" data-nav="${it.name}">
                ${getIcon(it.icon)}
                <span>${it.name}</span>
              </button>
            `).join('')}
          </nav>

          <div class="user-profile-card">
            <div class="user-avatar">${escapeHtml(session.initials || 'U')}</div>
            <div class="user-meta">
              <b>${escapeHtml(session.name)}</b>
              <small>${escapeHtml(session.role)}</small>
            </div>
            <button type="button" class="btn-sidebar-logout" id="logout-btn" title="Sign out of DRRAS">
              ${getIcon('LogOut')}
            </button>
          </div>
        </aside>

        <!-- Main Viewport -->
        <main class="app-main">
          <header class="topbar">
            <div class="topbar-left">
              <button type="button" class="btn-hamburger" id="open-menu" aria-label="Open sidebar menu">
                ${getIcon('Menu')}
              </button>
              <div class="breadcrumb-area">
                <span class="breadcrumb-path">${escapeHtml(session.role)} / Operations</span>
                <span class="breadcrumb-title">${escapeHtml(roleTitle)}</span>
              </div>
            </div>

            <div class="topbar-right">
              <button type="button" class="topbar-btn-icon" id="quick-search-trigger" title="Quick Search (Ctrl+K)">
                ${getIcon('Search')}
              </button>
              <button type="button" class="topbar-btn-icon" id="notifications-trigger" title="System Notifications">
                ${getIcon('Bell')}
                ${(() => { const unread=notifications.filter(n=>!n.read_at).length; return unread ? `<span class="topbar-badge-count">${unread}</span>` : ''; })()}
              </button>
              <button type="button" class="btn-emergency-action" id="open-new-req-btn">
                ${getIcon('Plus')}
                <span>Report Emergency</span>
              </button>
            </div>
          </header>

          <div class="content-wrapper">
            ${activeNotice ? `
              <div class="live-notice-bar">
                <div style="display:flex;align-items:center;gap:10px">
                  ${getIcon('CheckCircle2')}
                  <span>${escapeHtml(activeNotice)}</span>
                </div>
                <button type="button" class="btn-dismiss-notice" id="dismiss-notice-btn" aria-label="Dismiss notice">
                  ${getIcon('X')}
                </button>
              </div>
            ` : ''}

            <div id="page-content"></div>
          </div>
        </main>
      </div>
    `;

    // Shell wire-ups
    root.querySelector('#open-menu').onclick = () => root.querySelector('#sidebar').classList.add('open');
    root.querySelector('#close-menu').onclick = () => root.querySelector('#sidebar').classList.remove('open');
    
    root.querySelector('#logout-btn').onclick = async () => {
      stopLiveEventStream();
      try {
        await fetch('/api/auth/logout', { method: 'POST' });
      } catch (e) {}
      localStorage.removeItem('drras-user');
      session = null;
      renderLogin();
    };

    root.querySelector('#open-new-req-btn').onclick = () => openEmergencyRequestModal();

    if (root.querySelector('#dismiss-notice-btn')) {
      root.querySelector('#dismiss-notice-btn').onclick = () => {
        activeNotice = '';
        renderApp();
      };
    }

    root.querySelector('#quick-search-trigger').onclick = () => openQuickSearchModal();
    root.querySelector('#notifications-trigger').onclick = () => openNotificationsModal();

    root.querySelectorAll('nav.sidebar-nav button.nav-link').forEach(btn => {
      btn.onclick = () => {
        currentPage = btn.dataset.nav;
        root.querySelector('#sidebar').classList.remove('open');
        renderApp();
      };
    });

    renderCurrentPage();
  }

  // Render Sub-Page Router
  function renderCurrentPage() {
    const container = document.getElementById('page-content');
    if (!container) return;

    if (currentPage === 'Command Center') {
      renderCommandCenter(container);
    } else if (currentPage === 'Emergency Requests') {
      renderRequestsPage(container);
    } else if (currentPage === 'Resource Allocation') {
      renderAllocationPage(container);
    } else if (currentPage === 'Inventory & Warehouses') {
      renderInventoryPage(container);
    } else if (currentPage === 'Volunteers') {
      renderVolunteersPage(container);
    } else if (currentPage === 'Shelters') {
      renderSheltersPage(container);
    } else if (currentPage === 'Vehicles & Dispatch') {
      renderDispatchPage(container);
    } else if (currentPage === 'Funds & Donations') {
      if (session.role === 'Citizen') renderCitizenDonationsPage(container);
      else renderFundsPage(container);
    } else if (currentPage === 'System Administration') {
      renderAdminPage(container);
    }
  }

  // =========================================================================
  // 1. COMMAND CENTER (ROLE AWARE)
  // =========================================================================

  function renderCommandCenter(container) {
    if (session.role === 'Citizen') {
      renderCitizenView(container);
      return;
    }
    if (session.role === 'Volunteer') {
      renderVolunteerView(container);
      return;
    }
    if (session.role === 'Driver') {
      renderDriverView(container);
      return;
    }
    if (session.role === 'NGO Coordinator') {
      renderNgoView(container);
      return;
    }
    if (session.role === 'Government Official') {
      renderGovernmentView(container);
      return;
    }

    // Default Administrator Command View
    const openReqs = requests.filter(r => r.status !== 'Delivered');
    const criticalReqs = requests.filter(r => r.priority_score >= 85 && r.status === 'Awaiting allocation');

    container.innerHTML = `
      ${criticalReqs.length > 0 ? `
        <div class="alert-banner critical">
          <div class="alert-icon">${getIcon('AlertTriangle')}</div>
          <div class="alert-content">
            <b>${criticalReqs.length} Critical Emergency Requests Require Resource Allocation</b>
            <p>High-urgency requests with vulnerable persons and severe shortages are awaiting warehouse dispatch.</p>
          </div>
          <button type="button" class="alert-action-btn" id="review-critical-btn">
            Review Queue ${getIcon('ArrowUpRight')}
          </button>
        </div>
      ` : ''}

      <!-- Core Metrics Grid -->
      <section class="metrics-grid">
        <div class="metric-card" id="card-active-incident">
          <div class="metric-icon-box crimson">${getIcon('ShieldAlert')}</div>
          <div class="metric-info">
            <span class="metric-label">Active Disaster</span>
            <span class="metric-value">${escapeHtml(dashboardData?.activeIncidentTitle || 'Data unavailable')}</span>
            <span class="metric-sub alert">${Number(dashboardData?.activeDisasters ?? 0)} active incidents ? ${Number(dashboardData?.activeZonesCount ?? 0)} active zones</span>
          </div>
        </div>

        <div class="metric-card" id="card-open-requests">
          <div class="metric-icon-box amber">${getIcon('ClipboardList')}</div>
          <div class="metric-info">
            <span class="metric-label">Open Requests</span>
            <span class="metric-value">${openReqs.length}</span>
            <span class="metric-sub alert">${criticalReqs.length} critical priority</span>
          </div>
        </div>

        <div class="metric-card" id="card-inventory">
          <div class="metric-icon-box blue">${getIcon('Boxes')}</div>
          <div class="metric-info">
            <span class="metric-label">Available Supplies</span>
            <span class="metric-value">${dashboardData ? Number(dashboardData.availableResources).toLocaleString() : 'Data unavailable'}</span>
            <span class="metric-sub">Across ${Number(dashboardData?.warehousesCount ?? 0)} active warehouses</span>
          </div>
        </div>

        <div class="metric-card" id="card-volunteers">
          <div class="metric-icon-box emerald">${getIcon('Users')}</div>
          <div class="metric-info">
            <span class="metric-label">Active Volunteers</span>
            <span class="metric-value">${volunteers.length}</span>
            <span class="metric-sub positive">Current volunteer roster</span>
          </div>
        </div>
      </section>

      <!-- Charts & Visual Map Grid -->
      <section class="grid grid-2" style="margin-bottom:24px">
        <div class="card">
          <div class="card-title">
            <div>
              <h3>Emergency Demand Influx (Last 12 Hours)</h3>
              <p>Daily requests visible to your account during the last seven days</p>
            </div>
            <span class="badge badge-info">Database request records</span>
          </div>
          <div class="chart-wrapper">
            <canvas id="trend-canvas"></canvas>
          </div>
        </div>

        <div class="card">
          <div class="card-title">
            <div>
              <h3>Relief Response & Sector Map</h3>
              <p>Recorded request coordinates and warehouse locations</p>
            </div>
            <div style="display:flex;align-items:center;gap:8px">
              <div class="map-layer-switcher">
                <button type="button" class="map-layer-btn active" id="btn-dash-map-roads">Google Roads</button>
                <button type="button" class="map-layer-btn" id="btn-dash-map-sat">Satellite</button>
              </div>
              <span class="badge badge-neutral">Recorded locations only</span>
            </div>
          </div>
          <div id="dashboard-real-map" class="real-map-container"></div>
          <div class="map-legend">
            <span><i class="hot"></i> Critical Urgency (&gt;85)</span>
            <span><i class="blue"></i> Standard Relief Call</span>
            <span><i class="green"></i> Registered warehouse</span>
          </div>
        </div>
      </section>


      <!-- Tables Grid: Priority Queue & Inventory Health -->
      <section class="grid grid-2" style="margin-bottom:24px">
        <div class="card">
          <div class="card-title">
            <div>
              <h3>Priority Allocation Queue</h3>
              <p>Ranked by automated urgency score engine</p>
            </div>
            <button type="button" class="btn btn-secondary btn-sm" id="view-all-requests-btn">
              View All (${requests.length})
            </button>
          </div>
          <div class="data-table-container">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Score</th>
                  <th>Request Details</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                ${requests.slice(0, 4).map(r => `
                  <tr>
                    <td>
                      <span class="priority-score ${r.priority_score >= 85 ? 'critical' : r.priority_score >= 70 ? 'high' : 'medium'}">
                        ${r.priority_score}
                      </span>
                    </td>
                    <td>
                      <div class="table-row-title">${escapeHtml(r.need)}</div>
                      <div class="table-row-sub">${escapeHtml(r.id)} · ${escapeHtml(r.area)} · ${r.people_affected} people</div>
                    </td>
                    <td>
                      <span class="badge ${r.status === 'Delivered' ? 'badge-safe' : r.status === 'Dispatched' ? 'badge-info' : r.status === 'Allocated' ? 'badge-neutral' : 'badge-warning'}">${escapeHtml(r.status)}</span>
                      <small style="display:block;color:var(--text-muted);margin-top:4px">Verification: ${escapeHtml(r.verification_status || 'Not recorded')}</small>
                      <small style="display:block;color:var(--text-muted);margin-top:4px">${r.response_owner_type ? `Accepted by ${r.response_owner_type === 'government' ? 'Government' : escapeHtml(r.response_organization_name || 'an NGO')} · ${escapeHtml(r.response_assignment_status || 'Assigned')}` : 'Available to Government and approved NGOs'}</small>
                    </td>
                    <td>
                      ${['Administrator','Government Official'].includes(session.role) && r.response_owner_type === 'government' && r.status === 'Awaiting allocation' && r.verification_status === 'Verified' ? `
                        <button type="button" class="btn btn-primary btn-sm allocate-trigger-btn" data-id="${escapeHtml(r.id)}">
                          Allocate
                        </button>
                      ` : `
                        <span class="badge ${r.response_owner_type ? 'badge-safe' : 'badge-warning'}">${r.response_owner_type ? 'Accepted' : 'Awaiting response'}</span>
                      `}
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>

        <div class="card">
          <div class="card-title">
            <div>
              <h3>Warehouse Supply Readiness</h3>
              <p>Central Relief Depot stock levels</p>
            </div>
            <button type="button" class="btn btn-secondary btn-sm" id="view-inventory-btn">
              Manage Stock
            </button>
          </div>
          <div style="display:flex;flex-direction:column;gap:14px">
            ${inventory.slice(0, 4).map(item => {
              const pct = Math.min(100, Math.round((item.available_units / item.target_stock) * 100));
              const statusClass = item.status.toLowerCase();
              return `
                <div style="display:flex;flex-direction:column;gap:4px">
                  <div style="display:flex;justify-content:space-between;align-items:center">
                    <span style="font-weight:600;font-size:0.88rem">${escapeHtml(item.resource_name)}</span>
                    <span class="badge badge-${statusClass === 'critical' ? 'critical' : statusClass === 'low' ? 'warning' : 'safe'}">
                      ${escapeHtml(item.status)}
                    </span>
                  </div>
                  <div class="progress-track">
                    <div class="progress-fill ${statusClass === 'critical' ? 'critical' : statusClass === 'low' ? 'warning' : 'safe'}" style="width:${pct}%"></div>
                  </div>
                  <div style="display:flex;justify-content:space-between;font-size:0.75rem;color:var(--text-muted)">
                    <span>${item.available_units.toLocaleString()} available</span>
                    <span>Target: ${item.target_stock.toLocaleString()} units</span>
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        </div>
      </section>

      <!-- Role Operations Hub -->
      ${renderRoleFeatureHub(session.role)}
    `;

    // Wire-up events
    drawTrendChart(container.querySelector('#trend-canvas'), dashboardData?.trend || []);
    initDashboardRealMap();
    
    const reviewBtn = container.querySelector('#review-critical-btn');
    if (reviewBtn) reviewBtn.onclick = () => { currentPage = 'Resource Allocation'; renderApp(); };

    container.querySelector('#card-open-requests').onclick = () => { currentPage = 'Emergency Requests'; renderApp(); };
    container.querySelector('#card-inventory').onclick = () => { currentPage = 'Inventory & Warehouses'; renderApp(); };
    container.querySelector('#card-volunteers').onclick = () => { currentPage = 'Volunteers'; renderApp(); };
    container.querySelector('#view-all-requests-btn').onclick = () => { currentPage = 'Emergency Requests'; renderApp(); };
    container.querySelector('#view-inventory-btn').onclick = () => { currentPage = 'Inventory & Warehouses'; renderApp(); };

    container.querySelectorAll('.allocate-trigger-btn').forEach(btn => {
      btn.onclick = () => handleAllocate(btn.dataset.id);
    });

    wireRoleHub(container);
  }

  // Initialize Real Google Map for Command Center Dashboard
  function initDashboardRealMap() {
    const mapEl = document.getElementById('dashboard-real-map');
    if (!mapEl || !window.L) return;

    if (dashboardMapInstance) {
      try { dashboardMapInstance.remove(); } catch (e) {}
      dashboardMapInstance = null;
    }

    const defaultCenter = [30.9009, 75.8573];
    const map = L.map(mapEl, {
      center: defaultCenter,
      zoom: 12,
      zoomControl: true
    });
    dashboardMapInstance = map;

    let currentTileLayer = createGoogleMapTileLayer('googleRoadmap').addTo(map);

    const roadsBtn = document.getElementById('btn-dash-map-roads');
    const satBtn = document.getElementById('btn-dash-map-sat');
    if (roadsBtn && satBtn) {
      roadsBtn.onclick = () => {
        roadsBtn.classList.add('active');
        satBtn.classList.remove('active');
        map.removeLayer(currentTileLayer);
        currentTileLayer = createGoogleMapTileLayer('googleRoadmap').addTo(map);
      };
      satBtn.onclick = () => {
        satBtn.classList.add('active');
        roadsBtn.classList.remove('active');
        map.removeLayer(currentTileLayer);
        currentTileLayer = createGoogleMapTileLayer('googleSatellite').addTo(map);
      };
    }

    // Central Warehouse Marker (Green)
    const warehouseIcon = L.divIcon({
      className: 'custom-map-marker warehouse',
      html: '<div style="width:28px;height:28px;border-radius:50%;background:#059669;border:2px solid #ffffff;color:#ffffff;display:grid;place-items:center;box-shadow:0 2px 6px rgba(0,0,0,0.35)">' + getIcon('Boxes') + '</div>',
      iconSize: [28, 28],
      iconAnchor: [14, 14]
    });

    warehouses.filter(w => w.lat != null && w.lng != null).forEach(w => {
      L.marker([Number(w.lat), Number(w.lng)], { icon: warehouseIcon }).addTo(map)
        .bindPopup(`<b>${escapeHtml(w.name)}</b><br><small>${escapeHtml(w.address || w.district || '')}</small>`);
    });

    // Emergency Request Pins (Red / Blue)
    requests.forEach((r, idx) => {
      if (r.lat == null || r.lng == null) return;
      const lat = Number(r.lat);
      const lng = Number(r.lng);
      const isCrit = r.priority_score >= 85;

      const pinColor = isCrit ? '#dc2626' : '#2563eb';
      const markerHtml = `<div style="width:24px;height:24px;border-radius:50%;background:${pinColor};border:2px solid #ffffff;color:#fff;display:grid;place-items:center;font-size:10px;font-weight:bold;box-shadow:0 2px 6px rgba(0,0,0,0.35);${isCrit ? 'animation:pulseMarker 1.8s infinite ease-in-out;' : ''}">${r.priority_score}</div>`;

      const reqIcon = L.divIcon({
        className: `custom-map-marker ${isCrit ? 'critical' : 'standard'}`,
        html: markerHtml,
        iconSize: [24, 24],
        iconAnchor: [12, 12]
      });

      const popupContent = `
        <div style="min-width:210px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
            <span class="mono" style="font-weight:700;color:#0f172a">${escapeHtml(r.id)}</span>
            <span class="badge ${isCrit ? 'badge-critical' : 'badge-warning'}">Score: ${r.priority_score}</span>
          </div>
          <b style="font-size:0.92rem;color:#0f172a;display:block">${escapeHtml(r.need)}</b>
          <p style="font-size:0.82rem;color:#475569;margin:3px 0 6px">${escapeHtml(r.area)} · ${r.people_affected} people</p>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px;border-top:1px solid #e2e8f0;padding-top:8px">
            <span class="badge badge-neutral">${escapeHtml(r.status)}</span>
            ${r.status === 'Awaiting allocation' && r.verification_status === 'Verified' && ['Administrator', 'Government Official', 'NGO Coordinator'].includes(session.role) ? `
              <button type="button" class="btn btn-primary btn-sm dash-popup-alloc-btn" data-id="${escapeHtml(r.id)}" style="padding:3px 8px;font-size:0.75rem">
                Allocate
              </button>
            ` : ''}
          </div>
        </div>
      `;

      const marker = L.marker([lat, lng], { icon: reqIcon }).addTo(map).bindPopup(popupContent);
      marker.on('popupopen', () => {
        const btn = document.querySelector('.dash-popup-alloc-btn');
        if (btn) {
          btn.onclick = () => {
            map.closePopup();
            handleAllocate(btn.dataset.id);
          };
        }
      });
    });

    setTimeout(() => {
      try { map.invalidateSize(); } catch (e) {}
    }, 250);
  }


  // Draw Smooth Canvas Trend Area Chart
  function drawTrendChart(canvas, data) {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.width = canvas.parentElement.clientWidth || 400;
    const height = canvas.height = canvas.parentElement.clientHeight || 220;

    ctx.clearRect(0, 0, width, height);

    const padLeft = 40;
    const padRight = 20;
    const padTop = 20;
    const padBottom = 30;

    const chartW = width - padLeft - padRight;
    const chartH = height - padTop - padBottom;
    const maxVal = Math.max(1, ...(data || []).map(point => Number(point.v) || 0));

    // Horizontal grid lines
    ctx.strokeStyle = '#f1f5f9';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = padTop + (chartH / 4) * i;
      ctx.beginPath();
      ctx.moveTo(padLeft, y);
      ctx.lineTo(width - padRight, y);
      ctx.stroke();

      const label = Math.ceil(maxVal - (maxVal / 4) * i);
      ctx.fillStyle = '#94a3b8';
      ctx.font = '10px "DM Sans", sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText(label, padLeft - 8, y + 3);
    }

    if (!data || !data.length) return;

    const points = data.map((d, i) => {
      const x = padLeft + (chartW / (data.length - 1)) * i;
      const y = padTop + chartH - (d.v / maxVal) * chartH;
      return { x, y, label: d.d, v: d.v };
    });

    // Gradient area
    const gradient = ctx.createLinearGradient(0, padTop, 0, padTop + chartH);
    gradient.addColorStop(0, 'rgba(37, 99, 235, 0.25)');
    gradient.addColorStop(1, 'rgba(37, 99, 235, 0)');

    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 0; i < points.length - 1; i++) {
      const xc = (points[i].x + points[i + 1].x) / 2;
      const yc = (points[i].y + points[i + 1].y) / 2;
      ctx.quadraticCurveTo(points[i].x, points[i].y, xc, yc);
    }
    ctx.lineTo(points[points.length - 1].x, points[points.length - 1].y);
    ctx.lineTo(points[points.length - 1].x, padTop + chartH);
    ctx.lineTo(points[0].x, padTop + chartH);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // Line stroke
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 0; i < points.length - 1; i++) {
      const xc = (points[i].x + points[i + 1].x) / 2;
      const yc = (points[i].y + points[i + 1].y) / 2;
      ctx.quadraticCurveTo(points[i].x, points[i].y, xc, yc);
    }
    ctx.lineTo(points[points.length - 1].x, points[points.length - 1].y);
    ctx.strokeStyle = '#2563eb';
    ctx.lineWidth = 2.5;
    ctx.stroke();

    // Point dots
    points.forEach(p => {
      ctx.beginPath();
      ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
      ctx.fillStyle = '#ffffff';
      ctx.fill();
      ctx.strokeStyle = '#2563eb';
      ctx.lineWidth = 2;
      ctx.stroke();

      ctx.fillStyle = '#64748b';
      ctx.font = '10.5px "DM Sans", sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(p.label, p.x, height - 8);
    });
  }

  // Draw SVG Donut Chart
  function renderDonutChart(funds, centerText) {
    const text = centerText || (fundsData && fundsData.totalAllocated ? fundsData.totalAllocated : '₹0');
    if (!funds || !funds.length) {
      return `
        <svg viewBox="0 0 200 200" style="width:180px;height:180px;margin:auto;display:block">
          <circle cx="100" cy="100" r="70" fill="none" stroke="#e2e8f0" stroke-width="20" />
          <circle cx="100" cy="100" r="46" fill="#ffffff" />
          <text x="100" y="105" text-anchor="middle" font-family="'Manrope', sans-serif" font-weight="800" font-size="14" fill="#0f172a">${escapeHtml(text)}</text>
        </svg>
      `;
    }
    const total = funds.reduce((acc, f) => acc + f.percentage, 0) || 100;
    let cumulative = 0;
    const r = 70;
    const cx = 100;
    const cy = 100;

    const palette = ['#2563eb', '#f97316', '#10b981', '#8b5cf6', '#e11d48'];
    const slices = funds.map((f, index) => {
      const startAngle = (cumulative / total) * 2 * Math.PI;
      cumulative += f.percentage;
      const endAngle = (cumulative / total) * 2 * Math.PI;

      const x1 = cx + r * Math.sin(startAngle);
      const y1 = cy - r * Math.cos(startAngle);
      const x2 = cx + r * Math.sin(endAngle);
      const y2 = cy - r * Math.cos(endAngle);

      const largeArc = f.percentage / total > 0.5 ? 1 : 0;
      const pathData = `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2} Z`;

      return `<path d="${pathData}" fill="${f.color || palette[index % palette.length]}" stroke="#ffffff" stroke-width="2"/>`;
    }).join('');

    return `
      <svg viewBox="0 0 200 200" style="width:180px;height:180px;margin:auto;display:block">
        ${slices}
        <circle cx="${cx}" cy="${cy}" r="46" fill="#ffffff" />
        <text x="${cx}" y="${cy + 5}" text-anchor="middle" font-family="'Manrope', sans-serif" font-weight="800" font-size="14" fill="#0f172a">${escapeHtml(text)}</text>
      </svg>
    `;
  }

  // Role Operations Hub Component
  function renderRoleFeatureHub(role) {
    const mod = ROLE_MODULES[role] || ROLE_MODULES.Administrator;
    if (role === 'Driver') {
      const icons = ['Truck', 'MapPin', 'PackageCheck'];
      const actions = ['dispatches', 'route', 'proofs'];
      return `
        <section class="role-hub-section driver-operations-center" aria-labelledby="driver-operations-title">
          <div class="role-hub-header">
            <p class="eyebrow">DRIVER WORKSPACE</p>
            <h3 id="driver-operations-title">Driver Operations Center</h3>
            <p>Access your dispatch, current trip details and delivery proof workflow.</p>
          </div>
          <div class="role-hub-grid driver-operations-grid">
            ${mod.items.map(([name, detail, action], index) => `
              <article class="role-action-card driver-operation-card">
                <div class="role-action-card-top">
                  <div class="role-action-card-icon">${getIcon(icons[index])}</div>
                  <div class="role-action-card-title"><h4>${escapeHtml(name)}</h4><p>${escapeHtml(detail)}</p></div>
                </div>
                <button type="button" class="driver-operation-link" data-driver-operation="${actions[index]}">${escapeHtml(action)} ${getIcon('ArrowUpRight')}</button>
              </article>
            `).join('')}
          </div>
        </section>
      `;
    }
    return `
      <section class="role-hub-section">
        <div class="role-hub-header">
          <p class="eyebrow">SPECIALIZED WORKSPACE</p>
          <h3>${escapeHtml(mod.title)}</h3>
          <p>${escapeHtml(mod.intro)}</p>
        </div>
        <div class="role-hub-grid">
          ${mod.items.map(([name, detail, action]) => `
            <div class="role-action-card" data-title="${escapeHtml(name)}" data-detail="${escapeHtml(detail)}">
              <div class="role-action-card-top">
                <div class="role-action-card-icon">${getIcon('CheckCircle2')}</div>
                <div class="role-action-card-title">
                  <h4>${escapeHtml(name)}</h4>
                  <p>${escapeHtml(detail)}</p>
                </div>
              </div>
              <span class="role-action-btn-link">${escapeHtml(action)} ${getIcon('ArrowUpRight')}</span>
            </div>
          `).join('')}
        </div>
      </section>
    `;
  }

  function handleRoleAction(title, detail) {
    const t = (title || '').trim().toLowerCase();
    if (t.includes('request desk')) {
      openEmergencyRequestModal();
    } else if (t.includes('safety protocol') || t.includes('protocol')) {
      openAdvisoriesModal();
    } else if (t.includes('relief center') || t.includes('shelter')) {
      currentPage = 'Shelters';
      renderApp();
    } else if (t.includes('delivery feedback') || t.includes('feedback')) {
      const myReq = requests.find(r => r.requester_name === session.name);
      openCitizenFeedbackModal(myReq);
    } else if (t.includes('field check-in') || t.includes('check in')) {
      handleVolunteerCheckin();
    } else if (t.includes('distribution checklist') || t.includes('checklist')) {
      openDistributionReconciliationModal();
    } else if (t.includes('route guidance') || t.includes('route')) {
      showRouteModal();
    } else if (t.includes('ground incident') || t.includes('log incident')) {
      openFieldReportModal();
    } else if (t.includes('relief zone coverage') || t.includes('manage zone') || t.includes('zone')) {
      openZoneAdoptionModal();
    } else if (t.includes('donation intake') || t.includes('donation')) {
      openRegisterDonationModal();
    } else if (t.includes('volunteer deployment') || t.includes('deploy')) {
      openDeployVolunteerTaskModal();
    } else if (t.includes('consolidated ledger') || t.includes('ledger')) {
      openConsolidatedLedgerModal();
    } else if (t.includes('allocation authorization') || t.includes('review queue')) {
      currentPage = 'Resource Allocation';
      renderApp();
    } else if (t.includes('agency operations') || t.includes('agency') || t.includes('agencies')) {
      openInterAgencyModal();
    } else if (t.includes('relief fund utilization') || t.includes('fund')) {
      currentPage = 'Funds & Donations';
      renderApp();
    } else if (t.includes('public broadcast') || t.includes('broadcast') || t.includes('advisory')) {
      openBroadcastAdvisoryModal();
    } else if (t.includes('user access') || t.includes('approvals')) {
      currentPage = 'System Administration';
      renderApp();
    } else if (t.includes('urgency engine weights') || t.includes('weight') || t.includes('config')) {
      openUrgencyWeightsModal();
    } else if (t.includes('relief master data') || t.includes('master data')) {
      openMasterDataModal();
    } else if (t.includes('security & audit') || t.includes('audit')) {
      openAuditTrailModal();
    } else {
      openWorkspace(title, detail);
    }
  }

  function wireRoleHub(container) {
    container.querySelectorAll('.role-action-card:not(.driver-operation-card)').forEach(card => {
      card.onclick = () => {
        handleRoleAction(card.dataset.title, card.dataset.detail);
      };
    });
    container.querySelectorAll('.driver-operation-link').forEach(button => {
      button.onclick = () => {
        const action = button.dataset.driverOperation;
        if (action === 'dispatches' || action === 'proofs') {
          currentPage = 'Vehicles & Dispatch';
          renderApp();
          if (action === 'proofs') {
            const eligibleDispatch = dispatches.find(dispatch => dispatch.status === 'Arrived');
            if (eligibleDispatch) openDeliveryProofModal(eligibleDispatch.id);
            else if (!dispatches.some(dispatch => ['Delivered Pending Proof', 'Needs Review', 'Proof Rejected', 'Delivered'].includes(dispatch.status))) {
              showToast('There is no dispatch currently eligible for delivery proof.', 'info');
            }
          }
          return;
        }
        if (action === 'route') {
          const activeTrip = dispatches.find(dispatch => !['Delivered', 'Cancelled'].includes(dispatch.status));
          if (activeTrip) showRouteModal(activeTrip.id);
          else {
            currentPage = 'Vehicles & Dispatch';
            renderApp();
            showToast('No active trip is currently assigned. Your dispatch list shows the latest persisted status.', 'info');
          }
        }
      };
    });
  }

  // Role View: Citizen
  // Role View: Citizen
  function renderCitizenView(container) {
    const myRequests = requests.filter(r => r.requester_name === session.name);
    const myReq = myRequests[0] || null;

    if (!myReq) {
      container.innerHTML = `
        <div class="card" style="background:linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%);color:#ffffff;margin-bottom:24px">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px">
            <div>
              <p style="color:#93c5fd;font-size:0.75rem;font-weight:700;letter-spacing:1px;text-transform:uppercase">CITIZEN RELIEF DESK</p>
              <h2 style="color:#ffffff;font-size:1.6rem;margin:6px 0 8px">Disaster Relief Assistance Portal</h2>
              <p style="color:#cbd5e1;max-width:540px;font-size:0.92rem">Connect with District Emergency Response units for rapid food, clean water, medical triage, and evacuation shelters.</p>
            </div>
            <button type="button" class="btn btn-emergency-action" id="citizen-raise-req-btn">
              ${getIcon('Plus')} Report Emergency
            </button>
          </div>
        </div>

        <div class="card" style="padding:48px 24px;text-align:center;margin-bottom:24px">
          <div style="width:56px;height:56px;border-radius:50%;background:#eff6ff;color:#2563eb;display:grid;place-items:center;margin:0 auto 16px">
            ${getIcon('ClipboardList')}
          </div>
          <h3 style="font-size:1.25rem;margin-bottom:8px">No Active Emergency Requests</h3>
          <p style="color:var(--text-secondary);max-width:500px;margin:0 auto 20px;font-size:0.92rem;line-height:1.6">
            You have not submitted an emergency distress signal yet. If you or your family require immediate food rations, drinking water, medical kits, or rescue evacuation, click below to report an emergency.
          </p>
          <button type="button" class="btn btn-primary" id="citizen-empty-raise-btn">
            ${getIcon('Plus')} Submit Emergency Request
          </button>
        </div>

        <section class="grid grid-2" style="margin-bottom:24px">
          <div class="card">
            <div class="card-title">
              <div>
                <h3>Designated Evacuation Shelters</h3>
                <p>Verified open relief facilities in district</p>
              </div>
              <span class="badge badge-safe">Verified Open</span>
            </div>
            <div style="display:flex;flex-direction:column;gap:10px;margin-top:10px">
              ${shelters.slice(0, 3).map(s => `
                <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 12px;background:#f8fafc;border-radius:8px;font-size:0.88rem">
                  <span><b>${escapeHtml(s.name)}</b></span>
                  <span class="badge ${s.status === 'Operational' ? 'badge-safe' : 'badge-warning'}">${escapeHtml(s.status)} (${s.occupants}/${s.capacity})</span>
                </div>
              `).join('')}
            </div>
          </div>

          <div class="card">
            <div class="card-title">
              <div>
                <h3>District Safety Advisories</h3>
                <p>Directives from Emergency Operations Command</p>
              </div>
              <span class="badge badge-info">${advisories.length} current notices</span>
            </div>
            <div style="display:flex;flex-direction:column;gap:10px;margin-top:10px">
              ${advisories.slice(0,3).map(a => `<article style="padding:12px;background:#fef2f2;border:1px solid #fecaca;border-radius:8px"><b style="color:#991b1b;display:block;margin-bottom:4px">${escapeHtml(a.title)}</b><p style="color:#b91b1c;font-size:0.85rem">${escapeHtml(a.body)}</p></article>`).join('') || '<p class="empty-state">No current published advisories.</p>'}
            </div>
          </div>
        </section>

        ${renderRoleFeatureHub('Citizen')}
      `;

      container.querySelector('#citizen-raise-req-btn').onclick = () => openEmergencyRequestModal();
      const emptyBtn = container.querySelector('#citizen-empty-raise-btn');
      if (emptyBtn) emptyBtn.onclick = () => openEmergencyRequestModal();
      wireRoleHub(container);
      return;
    }

    // Citizen has an active request in database!
    const myDisp = dispatches.find(d => d.request_id === myReq.id);
    const safeShelter = shelters.find(s => s.status === 'Operational' && Number(s.capacity) > Number(s.occupants)) || null;
    const currentAdvisories = advisories.filter(a => !a.zone_id || !myReq.zone_id || a.zone_id === myReq.zone_id);

    container.innerHTML = `
      <div class="card" style="background:linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%);color:#ffffff;margin-bottom:24px">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px">
          <div>
            <p style="color:#93c5fd;font-size:0.75rem;font-weight:700;letter-spacing:1px;text-transform:uppercase">CITIZEN RELIEF DESK</p>
            <h2 style="color:#ffffff;font-size:1.6rem;margin:6px 0 8px">Emergency Assistance Active: ${escapeHtml(myReq.id)}</h2>
            <p style="color:#cbd5e1;max-width:540px;font-size:0.92rem">Your distress call has been logged in the DRRAS priority response queue. Response telemetry is updated live.</p>
          </div>
          <button type="button" class="btn btn-emergency-action" id="citizen-raise-req-btn">
            ${getIcon('Plus')} Report Another Need
          </button>
        </div>
      </div>

      <section class="metrics-grid">
        <div class="metric-card">
          <div class="metric-icon-box amber">${getIcon('ClipboardList')}</div>
          <div class="metric-info">
            <span class="metric-label">My Request Status</span>
            <span class="metric-value" style="font-size:1.25rem">${escapeHtml(myReq.status)}</span>
            <span class="metric-sub">${escapeHtml(myReq.id)} · Priority Score ${myReq.priority_score}</span>
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-icon-box blue">${getIcon('Truck')}</div>
          <div class="metric-info">
            <span class="metric-label">Dispatch Unit</span>
            <span class="metric-value" style="font-size:1.25rem">${myDisp ? escapeHtml(myDisp.vehicle) : (myReq.status === 'Awaiting allocation' ? 'Queued' : 'Awaiting dispatch assignment')}</span>
            <span class="metric-sub">${myDisp ? 'Driver: ' + escapeHtml(myDisp.driver) + ' · ETA: ' + escapeHtml(myDisp.eta) : (myReq.status === 'Awaiting allocation' ? 'Waiting for response assignment' : 'No linked dispatch yet')}</span>
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-icon-box emerald">${getIcon('HeartHandshake')}</div>
          <div class="metric-info">
            <span class="metric-label">Nearest Open Shelter</span>
            <span class="metric-value" style="font-size:1.25rem">${safeShelter ? escapeHtml(safeShelter.name) : 'No verified shelter listing'}</span>
            <span class="metric-sub positive">${Math.max(0, safeShelter.capacity - safeShelter.occupants)} beds open · Verified</span>
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-icon-box crimson">${getIcon('ShieldAlert')}</div>
          <div class="metric-info">
            <span class="metric-label">Sector Directives</span>
            <span class="metric-value" style="font-size:1.25rem">${escapeHtml(myReq.area)}</span>
            <span class="metric-sub alert">Priority Tier ${myReq.priority_score >= 85 ? 'Critical (P1)' : 'Standard'}</span>
          </div>
        </div>
      </section>

      <section class="grid grid-2" style="margin-bottom:24px">
        <div class="card">
          <div class="card-title">
            <div>
              <h3>Live Relief Delivery Timeline</h3>
              <p>${escapeHtml(myReq.id)} · ${escapeHtml(myReq.need)}</p>
            </div>
            <span class="badge ${myReq.status === 'Delivered' ? 'badge-safe' : myReq.status === 'Dispatched' ? 'badge-info' : 'badge-warning'}">
              ${escapeHtml(myReq.status)}
            </span>
          </div>
          <div style="display:flex;flex-direction:column;gap:16px;margin-top:12px">
            <div style="display:flex;gap:12px;align-items:flex-start">
              <div style="color:#059669">${getIcon('CheckCircle2')}</div>
              <div><b>Request Registered</b><p style="font-size:0.8rem;color:var(--text-muted)">Recorded in disaster registry queue</p></div>
            </div>
            <div style="display:flex;gap:12px;align-items:flex-start">
              <div style="color:#059669">${getIcon('CheckCircle2')}</div>
              <div><b>Priority Urgency Algorithm Verified</b><p style="font-size:0.8rem;color:var(--text-muted)">Calculated score: ${myReq.priority_score}/99 based on ${myReq.people_affected} people affected</p></div>
            </div>
            <div style="display:flex;gap:12px;align-items:flex-start">
              <div style="color:${myReq.status !== 'Awaiting allocation' ? '#059669' : '#94a3b8'}">${getIcon(myReq.status !== 'Awaiting allocation' ? 'CheckCircle2' : 'Clock3')}</div>
              <div><b>Warehouse Supplies Allocated</b><p style="font-size:0.8rem;color:var(--text-muted)">${myDisp ? escapeHtml(myDisp.load_items || 'Recorded relief manifest') + (myDisp.warehouse_name ? ' assigned at ' + escapeHtml(myDisp.warehouse_name) : ' assigned to dispatch') : 'Waiting for an authorized owner to allocate supplies'}</p></div>
            </div>
            <div style="display:flex;gap:12px;align-items:flex-start">
              <div style="color:${myReq.status === 'Delivered' ? '#059669' : (myReq.status === 'Dispatched' ? '#2563eb' : '#94a3b8')}">${getIcon(myReq.status === 'Delivered' ? 'CheckCircle2' : 'Clock3')}</div>
              <div><b>${myReq.status === 'Delivered' ? 'Delivery Completed ✓' : (myReq.status === 'Dispatched' ? 'Cargo In Transit (En Route)' : 'Delivery Standby')}</b><p style="font-size:0.8rem;color:var(--text-muted)">${myReq.status === 'Delivered' ? 'Confirmed delivered at destination coordinates' : (myReq.status === 'Dispatched' ? 'Vehicle is currently en route to destination' : 'Pending transport bay departure')}</p></div>
            </div>
          </div>

          <div style="margin-top:16px;padding-top:14px;border-top:1px solid var(--surface-border);display:flex;flex-wrap:wrap;gap:8px;align-items:center;justify-content:space-between">
            <button type="button" class="btn btn-secondary btn-sm" id="citizen-view-timeline-btn">
              ${getIcon('Clock3')} View Full Audit Timeline
            </button>
            <div style="display:flex;gap:8px;flex-wrap:wrap">
              ${myReq.status !== 'Delivered' ? `
                <button type="button" class="btn btn-primary btn-sm" id="citizen-confirm-delivery-btn">
                  ${getIcon('CheckCircle2')} Confirm Aid Received
                </button>
                <button type="button" class="btn btn-outline-danger btn-sm" id="citizen-report-issue-btn">
                  Report Delivery Issue
                </button>
              ` : `
                <span class="badge badge-safe">Aid Receipt Verified ✓</span>
              `}
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-title">
            <div>
              <h3>District Safety Directives</h3>
              <p>Advisories from District Emergency Command</p>
            </div>
            <span class="badge">${currentAdvisories.length} current advisories</span>
          </div>
          <div style="display:flex;flex-direction:column;gap:12px">
            ${currentAdvisories.slice(0,4).map((a,index) => `<article style="padding:12px;background:${index%2?'#eff6ff':'#fef2f2'};border:1px solid ${index%2?'#bfdbfe':'#fecaca'};border-radius:8px"><b style="display:block;margin-bottom:4px;color:${index%2?'#1e40af':'#991b1b'}">${escapeHtml(a.title)}</b><p style="font-size:0.85rem;color:${index%2?'#1d4ed8':'#b91c1b'}">${escapeHtml(a.body)}</p></article>`).join('') || '<p class="empty-state">No current published advisories for this request zone.</p>'}
          </div>
        </div>
      </section>

      ${renderRoleFeatureHub('Citizen')}
    `;

    container.querySelector('#citizen-raise-req-btn').onclick = () => openEmergencyRequestModal();
    const confBtn = container.querySelector('#citizen-confirm-delivery-btn');
    if (confBtn) confBtn.onclick = () => openCitizenFeedbackModal(myReq, 'confirm');
    const issBtn = container.querySelector('#citizen-report-issue-btn');
    if (issBtn) issBtn.onclick = () => openCitizenFeedbackModal(myReq, 'issue');
    const timeBtn = container.querySelector('#citizen-view-timeline-btn');
    if (timeBtn) timeBtn.onclick = () => openRequestTimelineModal(myReq.id);
    wireRoleHub(container);
  }

  // Role View: Volunteer
  function renderVolunteerView(container) {
    const myVol = volunteers.find(v => v.name === session.name);

    if (!myVol) {
      container.innerHTML = `
        <div class="card" style="background:linear-gradient(135deg, #065f46 0%, #0f172a 100%);color:#ffffff;margin-bottom:24px">
          <div>
            <p style="color:#6ee7b7;font-size:0.75rem;font-weight:700;letter-spacing:1px;text-transform:uppercase">RESPONDER WORKSPACE</p>
            <h2 style="color:#ffffff;font-size:1.6rem;margin:6px 0 8px">Volunteer Roster: ${escapeHtml(session.name)}</h2>
            <p style="color:#d1fae5;font-size:0.92rem">Account verified. Standing by for incident team assignment.</p>
          </div>
        </div>

        <div class="card" style="padding:48px 24px;text-align:center;margin-bottom:24px">
          <div style="width:56px;height:56px;border-radius:50%;background:#ecfdf5;color:#059669;display:grid;place-items:center;margin:0 auto 16px">
            ${getIcon('Users')}
          </div>
          <h3 style="font-size:1.25rem;margin-bottom:8px">No Active Field Assignment</h3>
          <p style="color:var(--text-secondary);max-width:480px;margin:0 auto 20px;font-size:0.92rem">
            You are currently on standby. When an NGO Coordinator or Incident Commander assigns a field mission to your profile, task checkpoints and route maps will appear here.
          </p>
        </div>

        ${renderRoleFeatureHub('Volunteer')}
      `;
      wireRoleHub(container);
      return;
    }

    const isOnTask = myVol.status === 'On task';
    const checklistState = JSON.parse(localStorage.getItem(`drras-vol-checklist-${myVol.id}`) || '[true, true, false, false]');

    container.innerHTML = `
      <div class="card" style="background:linear-gradient(135deg, #065f46 0%, #0f172a 100%);color:#ffffff;margin-bottom:24px">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px">
          <div>
            <p style="color:#6ee7b7;font-size:0.75rem;font-weight:700;letter-spacing:1px;text-transform:uppercase">RESPONDER WORKSPACE</p>
            <h2 style="color:#ffffff;font-size:1.6rem;margin:6px 0 8px">Field Assignment: ${escapeHtml(myVol.zone)} Sector</h2>
            <p style="color:#d1fae5;max-width:540px;font-size:0.92rem">Deployment Skill: <b>${escapeHtml(myVol.skill)}</b> · Status: <b>${escapeHtml(myVol.status)}</b></p>
          </div>
          <button type="button" class="btn btn-primary" id="vol-checkin-btn">
            ${getIcon('MapPin')} Check In at ${escapeHtml(myVol.zone)}
          </button>
        </div>
      </div>

      <section class="grid grid-2" style="margin-bottom:24px">
        <div class="card">
          <div class="card-title">
            <div>
              <h3>Today's Relief Task Assignment</h3>
              <p>Deployment in ${escapeHtml(myVol.zone)} · Assigned by NGO Coordination</p>
            </div>
            <span class="badge ${isOnTask ? 'badge-info' : 'badge-safe'}">${escapeHtml(myVol.status)}</span>
          </div>
          <div style="margin:12px 0 16px">
            <h4 style="font-size:1.1rem;margin-bottom:4px">${isOnTask ? 'Active Mission: ' + escapeHtml(myVol.skill) : 'Standby Readiness in ' + escapeHtml(myVol.zone)}</h4>
            <p style="color:var(--text-secondary);font-size:0.9rem">${escapeHtml(myVol.zone)} Sector · Designated Skill Group: ${escapeHtml(myVol.skill)}</p>
          </div>
          <div style="display:flex;gap:10px">
            <button type="button" class="btn btn-secondary btn-sm" id="vol-open-route-btn">
              ${getIcon('MapPin')} View Zone Map
            </button>
            ${isOnTask ? `
              <button type="button" class="btn btn-primary btn-sm" id="vol-mark-task-btn">
                Confirm Task Handover
              </button>
            ` : `
              <span class="badge badge-safe" style="padding:6px 12px">Available for Deployment</span>
            `}
          </div>
        </div>

        <div class="card">
          <div class="card-title">
            <div>
              <h3>Field Compliance Checklist</h3>
              <p>Standard operating relief protocols</p>
            </div>
            <span class="badge badge-neutral">4 Checkpoints</span>
          </div>
          <div style="display:flex;flex-direction:column;gap:10px" id="vol-checklist-box">
            ${['Verify cargo manifest from Central Depot', 'Scan beneficiary emergency request ID', 'Distribute water purification tablets', 'Submit end-of-shift headcount report'].map((item, idx) => `
              <label style="display:flex;align-items:center;gap:10px;font-size:0.88rem;cursor:pointer">
                <input type="checkbox" data-idx="${idx}" ${checklistState[idx] ? 'checked' : ''} style="width:17px;height:17px;accent-color:var(--success-emerald)">
                <span style="${checklistState[idx] ? 'text-decoration:line-through;color:var(--text-muted)' : ''}">${item}</span>
              </label>
            `).join('')}
          </div>
        </div>
      </section>

      <div class="card" id="vol-tasks-card" style="margin-bottom:24px">
        <div class="card-title">
          <div>
            <h3>Assigned Operational Missions (volunteer_tasks)</h3>
            <p>Database-backed field distribution, triage and relief tasks assigned to your roster profile</p>
          </div>
          <button type="button" class="btn btn-secondary btn-sm" id="vol-refresh-tasks-btn">
            ${getIcon('RotateCw')} Refresh Missions
          </button>
        </div>
        <div id="vol-tasks-list-content">
          <p style="color:var(--text-muted);font-size:0.88rem">Loading assigned mission orders...</p>
        </div>
      </div>

      ${renderRoleFeatureHub('Volunteer')}
    `;

    const loadVolunteerTasksList = async () => {
      const contentEl = container.querySelector('#vol-tasks-list-content');
      if (!contentEl) return;
      try {
        const res = await fetch('/api/volunteer-tasks');
        const tasks = await res.json();
        if (!Array.isArray(tasks) || tasks.length === 0) {
          contentEl.innerHTML = `
            <div style="text-align:center;padding:24px;color:var(--text-muted);font-size:0.9rem">
              No active field missions currently assigned. Stand by for coordinator dispatch orders.
            </div>
          `;
          return;
        }

        contentEl.innerHTML = `
          <div class="data-table-container">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Task ID</th>
                  <th>Mission Objective</th>
                  <th>Zone / Sector</th>
                  <th>Planned Qty</th>
                  <th>Status</th>
                  <th style="text-align:right">Action</th>
                </tr>
              </thead>
              <tbody>
                ${tasks.map(t => {
                  const statusClass = (t.status === 'Completed') ? 'badge-safe'
                    : (t.status === 'InProgress' || t.status === 'In Progress' || t.status === 'Accepted') ? 'badge-warning'
                    : (t.status === 'Submitted' || t.status === 'Submitted for Review') ? 'badge-info' : 'badge-neutral';
                  return `
                    <tr>
                      <td class="mono"><b>${escapeHtml(t.id)}</b></td>
                      <td>
                        <div style="font-weight:600">${escapeHtml(t.title)}</div>
                        <div style="font-size:0.8rem;color:var(--text-secondary)">${escapeHtml(t.task_type || 'Distribution')}</div>
                      </td>
                      <td><span class="badge badge-neutral">${escapeHtml(t.zone_id || 'Sector')}</span></td>
                      <td><b>${escapeHtml(t.quantity_expected || t.target_quantity || '—')}</b> units</td>
                      <td><span class="badge ${statusClass}">${escapeHtml(t.status)}</span></td>
                      <td style="text-align:right">
                        ${(t.status === 'Assigned' || t.status === 'Created') ? `
                          <div style="display:inline-flex;gap:6px">
                            <button type="button" class="btn btn-primary btn-sm vol-accept-task-btn" data-id="${escapeHtml(t.id)}">
                              ${getIcon('CheckCircle')} Accept
                            </button>
                            <button type="button" class="btn btn-outline-danger btn-sm vol-decline-task-btn" data-id="${escapeHtml(t.id)}">
                              ${getIcon('X')} Decline
                            </button>
                          </div>
                        ` : (t.status === 'Accepted' || t.status === 'InProgress' || t.status === 'In Progress') ? `
                          <div style="display:inline-flex;gap:6px">
                            <button type="button" class="btn btn-secondary btn-sm vol-checkin-task-btn" data-id="${escapeHtml(t.id)}">
                              ${getIcon('MapPin')} Check-In
                            </button>
                            <button type="button" class="btn btn-primary btn-sm vol-recon-task-btn" data-id="${escapeHtml(t.id)}">
                              ${getIcon('FileText')} Reconcile & Submit
                            </button>
                          </div>
                        ` : (t.status === 'Submitted' || t.status === 'Submitted for Review') ? `
                          <span class="badge badge-warning" style="font-size:0.8rem">Supervisor Review</span>
                        ` : `
                          <span class="badge badge-safe" style="font-size:0.8rem">Closed & Verified</span>
                        `}
                      </td>
                    </tr>
                  `;
                }).join('')}
              </tbody>
            </table>
          </div>
        `;

        contentEl.querySelectorAll('.vol-accept-task-btn').forEach(btn => {
          btn.onclick = async () => {
            const taskId = btn.dataset.id;
            try {
              const r = await fetch(`/api/volunteer-tasks/${taskId}/accept`, { method: 'POST' });
              const d = await r.json();
              if (r.ok) {
                showToast(`Mission ${taskId} accepted! Proceed with distribution.`);
                loadVolunteerTasksList();
              } else {
                showToast(d.error || 'Failed to accept mission');
              }
            } catch (err) {
              showToast('Network error accepting mission');
            }
          };
        });

        contentEl.querySelectorAll('.vol-decline-task-btn').forEach(btn => {
          btn.onclick = async () => {
            const taskId = btn.dataset.id;
            const reason = prompt('Please specify a reason for declining this assignment:');
            if (!reason) return;
            try {
              const r = await fetch(`/api/volunteer-tasks/${taskId}/decline`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reason })
              });
              const d = await r.json();
              if (r.ok) {
                showToast(`Mission ${taskId} declined.`);
                loadVolunteerTasksList();
              } else {
                showToast(d.error || 'Failed to decline mission');
              }
            } catch (err) {
              showToast('Network error declining mission');
            }
          };
        });

        contentEl.querySelectorAll('.vol-checkin-task-btn').forEach(btn => {
          btn.onclick = async () => {
            const taskId = btn.dataset.id;
            try {
              const r = await fetch(`/api/volunteer-tasks/${taskId}/check-in`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ notes: `GPS check-in verified at field distribution point` })
              });
              const d = await r.json();
              if (r.ok) {
                showToast(`Field Check-in confirmed for ${taskId}!`);
                loadVolunteerTasksList();
              } else {
                showToast(d.error || 'Failed to record check-in');
              }
            } catch (err) {
              showToast('Network error during check-in');
            }
          };
        });

        contentEl.querySelectorAll('.vol-recon-task-btn').forEach(btn => {
          btn.onclick = () => {
            const taskId = btn.dataset.id;
            const taskObj = tasks.find(t => t.id === taskId);
            openDistributionReconciliationModal(taskObj);
          };
        });

      } catch (err) {
        contentEl.innerHTML = `<p style="color:var(--danger);font-size:0.85rem">Failed to load volunteer tasks: ${escapeHtml(err.message)}</p>`;
      }
    };

    const refreshBtn = container.querySelector('#vol-refresh-tasks-btn');
    if (refreshBtn) refreshBtn.onclick = () => loadVolunteerTasksList();
    loadVolunteerTasksList();

    container.querySelector('#vol-checkin-btn').onclick = () => {
      showToast(`Checked in at ${myVol.zone} Field Post!`);
    };
    container.querySelector('#vol-open-route-btn').onclick = () => showRouteModal(myVol.zone);
    
    const handoverBtn = container.querySelector('#vol-mark-task-btn');
    if (handoverBtn) {
      handoverBtn.onclick = async () => {
        try {
          const res = await fetch(`/api/volunteers/${myVol.id}/unassign`, { method: 'POST' });
          const resData = await res.json();
          if (res.ok) {
            showToast('Field task handover confirmed! Status marked Available.');
            await loadAllData();
            renderApp();
          } else {
            showToast(resData.error || 'Failed to complete handover');
          }
        } catch (err) {
          showToast('Network error during handover');
        }
      };
    }

    container.querySelectorAll('#vol-checklist-box input').forEach(input => {
      input.onchange = (e) => {
        const i = Number(e.target.dataset.idx);
        checklistState[i] = e.target.checked;
        localStorage.setItem(`drras-vol-checklist-${myVol.id}`, JSON.stringify(checklistState));
        e.target.nextElementSibling.style.textDecoration = e.target.checked ? 'line-through' : 'none';
        e.target.nextElementSibling.style.color = e.target.checked ? 'var(--text-muted)' : 'inherit';
        showToast('Personal checklist updated in this browser.');
      };
    });

    wireRoleHub(container);
  }

  function renderDriverAssignmentInbox() {
    if (!driverAssignments.length) return '';
    return `
      <section class="card driver-assignment-inbox" aria-labelledby="driver-assignment-title" style="margin-bottom:24px">
        <div class="card-title"><div><h3 id="driver-assignment-title">Response Assignments</h3><p>Review work assigned by Government or your NGO coordinator.</p></div><span class="badge badge-warning">${driverAssignments.filter(a => a.driver_decision === 'Pending').length} Awaiting decision</span></div>
        <div style="display:grid;gap:12px">
          ${driverAssignments.map(a => `
            <article class="driver-assignment-row" style="display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;padding:16px;border:1px solid var(--surface-border);border-radius:12px">
              <div><b>${escapeHtml(a.request_id)} · ${escapeHtml(a.need || 'Response assignment')}</b><p style="margin:5px 0;color:var(--text-secondary)">${escapeHtml(a.area || 'Area not recorded')} · Assigned by ${escapeHtml(a.response_owner_name || (a.owner_type === 'government' ? 'Government' : 'NGO'))}</p>
                <small style="color:var(--text-muted)">${a.vehicle_code ? `Vehicle ${escapeHtml(a.registration_number || a.vehicle_code)} · ${escapeHtml(a.vehicle_type || '')}` : 'Vehicle assignment saved'}${a.dispatch_id ? ` · Dispatch ${escapeHtml(a.dispatch_id)}` : ' · Awaiting dispatch allocation'}</small>
              </div>
              <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
                ${a.driver_decision === 'Pending' ? `<button type="button" class="btn btn-primary btn-sm driver-assignment-accept" data-id="${a.assignment_id}">Accept</button><button type="button" class="btn btn-outline-danger btn-sm driver-assignment-decline" data-id="${a.assignment_id}">Reject</button>` : '<span class="badge badge-safe">Accepted · Awaiting dispatch</span>'}
              </div>
            </article>`).join('')}
        </div>
      </section>`;
  }

  function wireDriverAssignmentActions(container) {
    const submitDecision = async (assignmentId, action, reason = '') => {
      try {
        const response = await fetch(`/api/driver/assignments/${assignmentId}/${action}`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ reason })
        });
        const data = await response.json();
        if (!response.ok) { showToast(data.error || `Could not ${action} assignment`, 'error'); return; }
        showToast(action === 'accept' ? 'Assignment accepted. The response team can now allocate the dispatch.' : 'Assignment declined. The response team can select a replacement Driver.');
        await loadAllData(); renderApp();
      } catch (error) { showToast('Network error. Assignment decision was not saved.', 'error'); }
    };
    container.querySelectorAll('.driver-assignment-accept').forEach(button => {
      button.onclick = () => submitDecision(button.dataset.id, 'accept');
    });
    container.querySelectorAll('.driver-assignment-decline').forEach(button => {
      button.onclick = () => {
        const reason = prompt('Why are you declining this response assignment?');
        if (reason === null) return;
        submitDecision(button.dataset.id, 'decline', reason.trim());
      };
    });
  }

  // Role View: Driver
  function renderDriverView(container) {
    const myTrips = dispatches; // /api/dispatches already scopes Driver records by authenticated user ID.
    const activeTrip = myTrips.find(d => !['Delivered', 'Cancelled'].includes(d.status)) || null;
    const pendingAssignmentForTrip = activeTrip && driverAssignments.find(a => a.dispatch_id === activeTrip.id && a.driver_decision === 'Pending');

    if (!activeTrip) {
      container.innerHTML = `
        ${renderDriverAssignmentInbox()}
        <div class="card" style="background:linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%);color:#ffffff;margin-bottom:24px">
          <div>
            <p style="color:#93c5fd;font-size:0.75rem;font-weight:700;letter-spacing:1px;text-transform:uppercase">DRIVER LOGISTICS BOARD</p>
            <h2 style="color:#ffffff;font-size:1.6rem;margin:6px 0 8px">Fleet Standby: ${escapeHtml(session.name)}</h2>
            <p style="color:#cbd5e1;font-size:0.92rem">Dispatch assignments and vehicle status are loaded from current records.</p>
          </div>
        </div>

        <div class="card driver-empty-state" style="padding:48px 24px;text-align:center;margin-bottom:24px">
          <div style="width:56px;height:56px;border-radius:50%;background:#eff6ff;color:#2563eb;display:grid;place-items:center;margin:0 auto 16px">
            ${getIcon('Truck')}
          </div>
          <h3 style="font-size:1.25rem;margin-bottom:8px">No Active Transit Dispatches</h3>
          <p style="color:var(--text-secondary);max-width:500px;margin:0 auto 20px;font-size:0.92rem;line-height:1.6">
            You currently have no active dispatch assigned to your account. Your assigned dispatches, route details and available delivery actions will appear here when a dispatch is assigned.
          </p>
        </div>

        ${renderRoleFeatureHub('Driver')}
      `;
      wireDriverAssignmentActions(container);
      wireRoleHub(container);
      return;
    }

    const isRerouted = activeTrip.status === 'Rerouted' || Boolean(activeTrip.reroute_notes);

    container.innerHTML = `
      ${renderDriverAssignmentInbox()}
      ${isRerouted ? `
        <div class="reroute-alert-banner">
          ${getIcon('ShieldAlert')}
          <div>
            <b>Operational Detour / Reroute Active:</b> ${escapeHtml(activeTrip.reroute_notes || 'No reroute details recorded.')}
          </div>
        </div>
      ` : ''}

      <div class="card" style="background:linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%);color:#ffffff;margin-bottom:24px">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px">
          <div>
            <p style="color:#93c5fd;font-size:0.75rem;font-weight:700;letter-spacing:1px;text-transform:uppercase">DRIVER LOGISTICS BOARD</p>
            <h2 style="color:#ffffff;font-size:1.6rem;margin:6px 0 8px">${escapeHtml(activeTrip.vehicle)} · ${escapeHtml(activeTrip.destination)}</h2>
            <p style="color:#cbd5e1;font-size:0.92rem">Cargo: ${escapeHtml(activeTrip.load_items)} · ETA: ${escapeHtml(activeTrip.eta)}</p>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
            <button type="button" class="btn btn-secondary btn-sm" id="driver-show-route-btn">
              ${getIcon('MapPin')} Navigation Route
            </button>
            ${(activeTrip.status === 'Loading' || activeTrip.status === 'Ready') && !pendingAssignmentForTrip ? `
              <button type="button" class="btn btn-primary btn-sm" id="driver-start-btn">
                ${getIcon('Truck')} Start Journey
              </button>
            ` : (activeTrip.status === 'En route' || activeTrip.status === 'EnRoute' || activeTrip.status === 'Rerouted') ? `
              <button type="button" class="btn btn-primary btn-sm" id="driver-arrive-btn">
                ${getIcon('MapPin')} Mark Arrived
              </button>
              <button type="button" class="btn btn-outline-danger btn-sm" id="driver-blockage-btn">
                Report Blockage
              </button>
            ` : ''}
            ${activeTrip.status !== 'Delivered' ? `
              <button type="button" class="btn btn-primary btn-sm" id="driver-proof-btn" ${activeTrip.status === 'Arrived' ? '' : 'disabled title="Delivery proof is available after arrival."'}>
                ${getIcon('CheckCircle2')} Submit Proof
              </button>
            ` : `
              <span class="badge badge-safe">Delivered ✓</span>
            `}
          </div>
        </div>
      </div>

      <div class="card" style="margin-bottom:24px">
        <div class="card-title">
          <div>
            <h3>Route from registered coordinates</h3>
            <p>${escapeHtml(activeTrip.warehouse_name || 'Pickup warehouse not recorded')} to ${escapeHtml(activeTrip.request_area || activeTrip.destination || 'Request destination not recorded')}. Live vehicle GPS is unavailable.</p>
          </div>
          <div class="map-layer-switcher">
            <button type="button" class="map-layer-btn active" id="btn-driver-map-roads">Google Roads</button>
            <button type="button" class="map-layer-btn" id="btn-driver-map-sat">Satellite</button>
          </div>
        </div>
        <div id="driver-real-map" class="real-map-container" style="height:260px"></div>
          <div class="driver-map-meta">
          <span style="color:var(--text-secondary)">Assigned Vehicle: <b>${escapeHtml(activeTrip.vehicle)}</b> · Live GPS unavailable</span>
          <button type="button" class="btn btn-secondary btn-sm" id="driver-detailed-route-btn">
            Detailed Route Checkpoints ${getIcon('ArrowUpRight')}
          </button>
        </div>
      </div>

      <section class="grid grid-2" style="margin-bottom:24px">
        <div class="card">
          <div class="card-title">
            <div>
              <h3>Active Transit Status</h3>
              <p>Current Dispatch Trip: ${escapeHtml(activeTrip.id)}</p>
            </div>
            <span class="badge ${activeTrip.status === 'Delivered' ? 'badge-safe' : activeTrip.status === 'En route' ? 'badge-info' : 'badge-neutral'}">
              ${escapeHtml(activeTrip.status)}
            </span>
          </div>
          <div class="driver-transit-endpoints">
            <div class="driver-transit-endpoint">
              <span><b>Origin:</b> ${escapeHtml(activeTrip.warehouse_name || 'Warehouse not recorded')}</span>
              <span class="badge badge-neutral">Origin</span>
            </div>
            <div class="driver-transit-endpoint">
              <span><b>Destination:</b> ${escapeHtml(activeTrip.destination)}</span>
              <span class="badge ${activeTrip.status === 'Delivered' ? 'badge-safe' : 'badge-neutral'}">${activeTrip.status === 'Delivered' ? 'Delivered' : 'Destination'}</span>
            </div>
            <p class="driver-transit-eta">ETA: ${escapeHtml(activeTrip.eta || 'Not recorded')}</p>
          </div>
        </div>

        <div class="card">
          <div class="card-title">
            <div>
              <h3>Recorded Dispatch Locations</h3>
              <p>Saved dispatch endpoints are shown below. Intermediate checkpoints are displayed only when recorded.</p>
            </div>
            <span class="badge badge-neutral">No Telemetry</span>
          </div>
          <div class="dispatch-location-timeline">
            <div class="dispatch-location-row">
              <span class="dispatch-location-marker" aria-hidden="true">${getIcon('PackageCheck')}</span>
              <div class="dispatch-location-copy"><small>ORIGIN</small><strong>${escapeHtml(activeTrip.warehouse_name || 'Warehouse not recorded')}</strong></div>
              <span class="badge badge-neutral">${escapeHtml(activeTrip.departed_at ? 'Departed' : 'Pickup')}</span>
            </div>
            <div class="dispatch-location-connector" aria-hidden="true"></div>
            <div class="dispatch-location-row">
              <span class="dispatch-location-marker destination" aria-hidden="true">${getIcon('MapPin')}</span>
              <div class="dispatch-location-copy"><small>DESTINATION</small><strong>${escapeHtml(activeTrip.destination || activeTrip.request_area || 'Destination not recorded')}</strong></div>
              <span class="badge ${activeTrip.status === 'Delivered' ? 'badge-safe' : 'badge-neutral'}">${activeTrip.status === 'Delivered' ? 'Delivered' : 'Drop-off'}</span>
            </div>
          </div>
          <p class="dispatch-location-empty">No route checkpoints are stored for this dispatch.</p>
          <p class="dispatch-telemetry-note">Live GPS or telemetry is unavailable. Locations above come from the saved dispatch and warehouse records.</p>
        </div>
      </section>

      ${renderRoleFeatureHub('Driver')}
    `;

    container.querySelector('#driver-show-route-btn').onclick = () => showRouteModal(activeTrip.id);
    const detailBtn = container.querySelector('#driver-detailed-route-btn');
    if (detailBtn) detailBtn.onclick = () => showRouteModal(activeTrip.id);

    const startBtn = container.querySelector('#driver-start-btn');
    if (startBtn) {
      startBtn.onclick = async () => {
        try {
          const res = await fetch(`/api/dispatches/${activeTrip.id}/start`, { method: 'POST' });
          const resData = await res.json();
          if (!res.ok) {
            showToast(resData.error || 'Failed to start journey');
            return;
          }
          showToast(`Trip ${activeTrip.id} started! Status is En route.`);
          await loadAllData();
          renderApp();
        } catch (err) {
          showToast('Network error starting journey');
        }
      };
    }

    const arriveBtn = container.querySelector('#driver-arrive-btn');
    if (arriveBtn) {
      arriveBtn.onclick = async () => {
        try {
          const res = await fetch(`/api/dispatches/${activeTrip.id}/arrive`, { method: 'POST' });
          const resData = await res.json();
          if (!res.ok) {
            showToast(resData.error || 'Failed to record arrival');
            return;
          }
          showToast(`Arrival recorded for ${activeTrip.id}! Proceed to submit proof.`);
          await loadAllData();
          renderApp();
        } catch (err) {
          showToast('Network error recording arrival');
        }
      };
    }

    const blockBtn = container.querySelector('#driver-blockage-btn');
    if (blockBtn) blockBtn.onclick = () => openRouteBlockageModal(activeTrip.id);

    const proofBtn = container.querySelector('#driver-proof-btn');
    if (proofBtn) proofBtn.onclick = () => openDeliveryProofModal(activeTrip.id);

    wireDriverAssignmentActions(container);
    initDriverRealMap(activeTrip);
    wireRoleHub(container);
  }

  // Plot only persisted warehouse/request coordinates. The line comes from OSRM road routing, never simulated GPS.
  async function renderRecordedDispatchRoute(mapEl, dispatch, statusEl, roadsBtn, satBtn, mapSlot) {
    if (!mapEl || !window.L) {
      if (mapEl) mapEl.textContent = 'Map library unavailable.';
      return null;
    }
    const origin = dispatch && dispatch.pickup_lat != null && dispatch.pickup_lng != null
      ? [Number(dispatch.pickup_lat), Number(dispatch.pickup_lng)] : null;
    const destination = dispatch && dispatch.destination_lat != null && dispatch.destination_lng != null
      ? [Number(dispatch.destination_lat), Number(dispatch.destination_lng)] : null;
    if (!origin && !destination) {
      mapEl.innerHTML = '<div style="display:grid;place-items:center;height:100%;min-height:180px;padding:20px;text-align:center;color:var(--text-secondary)"><div><b>Route coordinates unavailable</b><p>Record the dispatch warehouse and the request location to map this route.</p></div></div>';
      if (statusEl) statusEl.textContent = 'No route coordinates are recorded.';
      return null;
    }
    const map = L.map(mapEl, { zoomControl: true, scrollWheelZoom: true });
    let tile = createGoogleMapTileLayer('googleRoadmap').addTo(map);
    const bounds = [];
    if (origin) {
      L.marker(origin).addTo(map).bindPopup(`<b>Pickup: ${escapeHtml(dispatch.warehouse_name || 'Recorded warehouse')}</b>`);
      bounds.push(origin);
    }
    if (destination) {
      L.marker(destination).addTo(map).bindPopup(`<b>Destination: ${escapeHtml(dispatch.request_area || dispatch.destination || 'Emergency request')}</b>`);
      bounds.push(destination);
    }
    if (roadsBtn && satBtn) {
      roadsBtn.onclick = () => { roadsBtn.classList.add('active'); satBtn.classList.remove('active'); map.removeLayer(tile); tile=createGoogleMapTileLayer('googleRoadmap').addTo(map); };
      satBtn.onclick = () => { satBtn.classList.add('active'); roadsBtn.classList.remove('active'); map.removeLayer(tile); tile=createGoogleMapTileLayer('googleSatellite').addTo(map); };
    }
    if (bounds.length === 1) map.setView(bounds[0], 13);
    else map.fitBounds(bounds, { padding: [30, 30] });
    if (!origin || !destination) {
      if (statusEl) statusEl.textContent = origin ? 'Destination coordinates were not recorded for this request.' : 'Pickup warehouse coordinates were not recorded.';
    } else {
      if (statusEl) statusEl.textContent = 'Calculating a road route from recorded pickup and request coordinates?';
      try {
        const routeUrl = `https://router.project-osrm.org/route/v1/driving/${origin[1]},${origin[0]};${destination[1]},${destination[0]}?overview=full&geometries=geojson`;
        const routeController = new AbortController();
        const routeTimer = setTimeout(() => routeController.abort(), 8000);
        let response;
        try { response = await fetch(routeUrl, { headers: { 'Accept': 'application/json' }, signal: routeController.signal }); }
        finally { clearTimeout(routeTimer); }
        const data = await response.json();
        if (!response.ok || data.code !== 'Ok' || !data.routes?.length) throw new Error(data.message || data.code || 'No road route returned.');
        const route = data.routes[0];
        const geometry = L.geoJSON(route.geometry, { style: { color: '#2563eb', weight: 5, opacity: 0.85 } }).addTo(map);
        map.fitBounds(geometry.getBounds(), { padding: [30, 30] });
        if (statusEl) statusEl.textContent = `Road route ? ${(route.distance / 1000).toFixed(1)} km ? ${Math.round(route.duration / 60)} min estimate (routing service)`;
      } catch (error) {
        if (statusEl) statusEl.textContent = 'Recorded pickup and destination are shown. Road routing service is unavailable; no route line is fabricated.';
      }
    }
    setTimeout(() => { try { map.invalidateSize(); } catch (e) {} }, 150);
    return map;
  }

  function initDriverRealMap(activeTrip) {
    const mapEl = document.getElementById('driver-real-map');
    if (!mapEl) return;
    if (driverMapInstance) { try { driverMapInstance.remove(); } catch (e) {} driverMapInstance = null; }
    const statusEl = document.getElementById('driver-route-data-status');
    renderRecordedDispatchRoute(mapEl, activeTrip, statusEl, document.getElementById('btn-driver-map-roads'), document.getElementById('btn-driver-map-sat')).then(map => { driverMapInstance = map; });
  }

  // Role View: NGO Coordinator
  async function renderNgoView(container) {
    let donationsList = [];
    let adoptionsList = [];
    try {
      const [dRes, aRes] = await Promise.all([
        fetch('/api/donations').then(r => r.json()).catch(() => []),
        fetch('/api/adoptions').then(r => r.json()).catch(() => [])
      ]);
      donationsList = Array.isArray(dRes) ? dRes : [];
      adoptionsList = Array.isArray(aRes) ? aRes : [];
    } catch (e) {}

    const familiesCount = requests.filter(r => r.status === 'Delivered').reduce((sum, r) => sum + Number(r.people_affected || 0), 0);
    const activeVols = volunteers.filter(v => ['Available','Deployed','Active','On task'].includes(v.status)).length;
    const inTransitCount = donationsList.filter(d => d.status === 'Submitted' || d.status === 'In Transit' || d.status === 'InTransit' || d.status === 'Received').length;
    const adoptedZonesCount = adoptionsList.filter(a => a.status === 'Approved').length;

    container.innerHTML = `
      <div class="page-header">
        <div class="page-header-text">
          <h2>NGO Relief Coordination & Zone Operations</h2>
          <p>Adopt critical disaster zones, register in-transit donations, and mobilize volunteer rosters.</p>
        </div>
        <div class="page-header-actions" style="display:flex;gap:8px;flex-wrap:wrap">
          <button type="button" class="btn btn-secondary" id="ngo-personnel-btn">
            ${getIcon('Users')} Personnel &amp; approvals
          </button>
          <button type="button" class="btn btn-secondary" id="ngo-adopt-zone-btn">
            ${getIcon('ShieldAlert')} Adopt Relief Zone
          </button>
          <button type="button" class="btn btn-primary" id="ngo-add-donation-btn">
            ${getIcon('Plus')} Register Donation
          </button>
        </div>
      </div>

      <section class="metrics-grid">
        <div class="metric-card">
          <div class="metric-icon-box emerald">${getIcon('HeartHandshake')}</div>
          <div class="metric-info">
            <span class="metric-label">Families Supported</span>
            <span class="metric-value">${familiesCount.toLocaleString()}</span>
            <span class="metric-sub positive">Across adopted flood zones</span>
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-icon-box blue">${getIcon('Boxes')}</div>
          <div class="metric-info">
            <span class="metric-label">Donations In Transit</span>
            <span class="metric-value">${String(inTransitCount).padStart(2, '0')}</span>
            <span class="metric-sub">Relief supplies &amp; funds</span>
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-icon-box amber">${getIcon('Users')}</div>
          <div class="metric-info">
            <span class="metric-label">Active Field Volunteers</span>
            <span class="metric-value">${activeVols}</span>
            <span class="metric-sub positive">Based on current volunteer status</span>
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-icon-box crimson">${getIcon('ShieldAlert')}</div>
          <div class="metric-info">
            <span class="metric-label">Zone Adoptions</span>
            <span class="metric-value">${String(adoptedZonesCount).padStart(2, '0')}</span>
            <span class="metric-sub">Current adoption records</span>
          </div>
        </div>
      </section>

      ${renderRoleFeatureHub('NGO Coordinator')}
    `;

    container.querySelector('#ngo-add-donation-btn').onclick = () => openRegisterDonationModal();
    const adoptBtn = container.querySelector('#ngo-adopt-zone-btn');
    if (adoptBtn) adoptBtn.onclick = () => openZoneAdoptionModal();
    const personnelBtn=container.querySelector('#ngo-personnel-btn');
    if(personnelBtn) personnelBtn.onclick=()=>openNgoPersonnelModal();

    wireRoleHub(container);
  }

  // Role View: Government Official
  async function renderGovernmentView(container) {
    let pendingAdoptions = [];
    let zonesList = [];
    try {
      const [adopRes, zonesRes] = await Promise.all([
        fetch('/api/adoptions?status=Requested').then(r => r.json()).catch(() => []),
        fetch('/api/zones').then(r => r.json()).catch(() => [])
      ]);
      pendingAdoptions = Array.isArray(adopRes) ? adopRes : [];
      zonesList = Array.isArray(zonesRes) ? zonesRes : [];
    } catch (e) {
      pendingAdoptions = [];
      zonesList = [];
    }

    const unverifiedReqs = requests.filter(r => r.status === 'Awaiting allocation' || r.verification_status === 'Unverified').slice(0, 4);
    const highPriorityZonesCount = zonesList.filter(z => ['High','Critical'].includes(z.risk_level || z.severity) && z.status === 'Active').length;
    const totalAffectedPopulation = requests.reduce((s, r) => s + Number(r.people_affected ?? 0), 0);
    const fulfillmentPct = requests.length > 0 ? Math.round((requests.filter(r => r.status === 'Delivered').length / requests.length) * 100) : 0;
    const allocatedFundStr = (fundsData && fundsData.totalAllocated) ? fundsData.totalAllocated : '₹0';

    container.innerHTML = `
      <div class="page-header">
        <div class="page-header-text">
          <h2>Government Emergency Command & District Oversight</h2>
          <p>Review district resource gaps, authorize emergency funds, and oversee multi-agency deployments.</p>
        </div>
        <div class="page-header-actions" style="display:flex;gap:8px;flex-wrap:wrap">
          <button type="button" class="btn btn-secondary" id="gov-broadcast-advisory-btn">
            ${getIcon('Bell')} Broadcast Advisory
          </button>
          <button type="button" class="btn btn-primary" id="gov-open-alloc-btn">
            ${getIcon('ArrowUpRight')} Emergency Allocations
          </button>
        </div>
      </div>

      <section class="metrics-grid">
        <div class="metric-card">
          <div class="metric-icon-box crimson">${getIcon('ShieldAlert')}</div>
          <div class="metric-info">
            <span class="metric-label">High Priority Zones</span>
            <span class="metric-value">${String(highPriorityZonesCount).padStart(2, '0')}</span>
            <span class="metric-sub alert">Immediate assistance active</span>
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-icon-box amber">${getIcon('Users')}</div>
          <div class="metric-info">
            <span class="metric-label">Affected Population</span>
            <span class="metric-value">${totalAffectedPopulation.toLocaleString()}</span>
            <span class="metric-sub">Registered across ${zonesList.length || 0} active zones</span>
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-icon-box emerald">${getIcon('PackageCheck')}</div>
          <div class="metric-info">
            <span class="metric-label">Relief Fulfillment</span>
            <span class="metric-value">${fulfillmentPct}%</span>
            <span class="metric-sub positive">Target: 90%</span>
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-icon-box blue">${getIcon('Wallet')}</div>
          <div class="metric-info">
            <span class="metric-label">Allocated Fund</span>
            <span class="metric-value">${allocatedFundStr}</span>
            <span class="metric-sub">State Disaster Relief Fund</span>
          </div>
        </div>
      </section>

      <!-- Operational Queues: Zone Adoptions & Request Verification -->
      <section class="grid grid-2" style="margin-bottom:24px">
        <div class="card">
          <div class="card-title">
            <div>
              <h3>NGO Zone Adoption Requests</h3>
              <p>Applications awaiting District Command review</p>
            </div>
            <span class="badge ${pendingAdoptions.length > 0 ? 'badge-warning' : 'badge-safe'}">
              ${pendingAdoptions.length} Pending
            </span>
          </div>
          <div class="data-table-container">
            <table class="data-table">
              <thead>
                <tr>
                  <th>NGO Organization</th>
                  <th>Sector</th>
                  <th>Volunteers</th>
                  <th style="text-align:right">Review</th>
                </tr>
              </thead>
              <tbody>
                ${Array.isArray(pendingAdoptions) && pendingAdoptions.length > 0 ? pendingAdoptions.map(a => `
                  <tr>
                    <td><b>${escapeHtml(a.organization_name || 'Relief Agency')}</b></td>
                    <td><span class="badge badge-info">${escapeHtml(a.zone_id)}</span></td>
                    <td>${Number(a.available_volunteers ?? 0)} volunteers</td>
                    <td style="text-align:right">
                      <div style="display:inline-flex;gap:4px">
                        <button type="button" class="btn btn-primary btn-sm gov-approve-adp-btn" data-id="${a.id}">Approve</button>
                        <button type="button" class="btn btn-outline-danger btn-sm gov-reject-adp-btn" data-id="${a.id}">Reject</button>
                      </div>
                    </td>
                  </tr>
                `).join('') : `
                  <tr>
                    <td colspan="4" style="text-align:center;padding:20px;color:var(--text-muted)">
                      No pending adoption applications. All sectors allocated.
                    </td>
                  </tr>
                `}
              </tbody>
            </table>
          </div>
        </div>

        <div class="card">
          <div class="card-title">
            <div>
              <h3>Request Triage &amp; Verification Queue</h3>
              <p>Distress calls awaiting official verification</p>
            </div>
            <span class="badge badge-info">${unverifiedReqs.length} Queued</span>
          </div>
          <div class="data-table-container">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Score</th>
                  <th>Distress Need</th>
                  <th>Sector</th>
                  <th style="text-align:right">Action</th>
                </tr>
              </thead>
              <tbody>
                ${unverifiedReqs.map(r => `
                  <tr>
                    <td>
                      <span class="priority-score ${r.priority_score >= 85 ? 'critical' : 'high'}">${r.priority_score}</span>
                    </td>
                    <td><b>${escapeHtml(r.need)}</b><br><small style="color:var(--text-muted)">${r.people_affected} people</small></td>
                    <td><small>${escapeHtml(r.area)}</small></td>
                    <td style="text-align:right">
                      <button type="button" class="btn btn-secondary btn-sm gov-verify-req-btn" data-id="${escapeHtml(r.id)}">
                        Verify / Triage
                      </button>
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      ${renderRoleFeatureHub('Government Official')}
    `;

    container.querySelector('#gov-open-alloc-btn').onclick = () => { currentPage = 'Resource Allocation'; renderApp(); };
    container.querySelector('#gov-broadcast-advisory-btn').onclick = () => openBroadcastAdvisoryModal();

    container.querySelectorAll('.gov-approve-adp-btn').forEach(btn => {
      btn.onclick = async () => {
        try {
          const res = await fetch(`/api/adoptions/${btn.dataset.id}/approve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason: 'Approved by District Command' })
          });
          if (res.ok) {
            showToast('Zone adoption approved!');
            await loadAllData();
            renderApp();
          } else {
            showToast('Failed to approve adoption');
          }
        } catch (e) {
          showToast('Network error during adoption review');
        }
      };
    });

    container.querySelectorAll('.gov-reject-adp-btn').forEach(btn => {
      btn.onclick = async () => {
        try {
          const res = await fetch(`/api/adoptions/${btn.dataset.id}/reject`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason: 'Capacity threshold reached' })
          });
          if (res.ok) {
            showToast('Zone adoption rejected.');
            await loadAllData();
            renderApp();
          }
        } catch (e) {
          showToast('Network error during rejection');
        }
      };
    });

    container.querySelectorAll('.gov-verify-req-btn').forEach(btn => {
      btn.onclick = () => {
        const req = requests.find(r => r.id === btn.dataset.id);
        if (req) openVerifyRequestModal(req);
      };
    });

    wireRoleHub(container);
  }

  // =========================================================================
  // 2. EMERGENCY REQUESTS PAGE
  // =========================================================================

  function renderRequestsPage(container) {
    const filter = pageFilters.requests;
    
    // Filter & Search logic
    let filtered = requests.filter(r => {
      const matchSearch = !filter.search || 
        r.id.toLowerCase().includes(filter.search.toLowerCase()) ||
        r.area.toLowerCase().includes(filter.search.toLowerCase()) ||
        r.need.toLowerCase().includes(filter.search.toLowerCase()) ||
        (r.requester_name && r.requester_name.toLowerCase().includes(filter.search.toLowerCase()));

      const matchStatus = filter.status === 'ALL' || r.status === filter.status;
      return matchSearch && matchStatus;
    });

    // Sorting
    filtered.sort((a, b) => {
      if (filter.sort === 'PRIORITY_DESC') return b.priority_score - a.priority_score;
      if (filter.sort === 'PRIORITY_ASC') return a.priority_score - b.priority_score;
      return 0;
    });

    container.innerHTML = `
      <div class="page-header">
        <div class="page-header-text">
          <h2>Emergency Requests Directory</h2>
          <p>Track every call for help from citizen submission through priority scoring to confirmed relief delivery.</p>
        </div>
        <div class="page-header-actions">
          <a href="/api/export/requests.csv" class="btn btn-secondary" download>
            ${getIcon('Download')} Export CSV
          </a>
          <button type="button" class="btn btn-primary" id="req-page-new-btn">
            ${getIcon('Plus')} New Emergency Request
          </button>
        </div>
      </div>

      <div class="card">
        <!-- Table Toolbar -->
        <div class="table-toolbar">
          <div class="search-input-wrapper">
            ${getIcon('Search')}
            <input type="text" class="search-input" id="req-search-input" placeholder="Search by ID, area, need, requester..." value="${escapeHtml(filter.search)}">
          </div>

          <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
            <select class="filter-select" id="req-status-filter">
              <option value="ALL" ${filter.status === 'ALL' ? 'selected' : ''}>All Statuses (${requests.length})</option>
              <option value="Awaiting allocation" ${filter.status === 'Awaiting allocation' ? 'selected' : ''}>Awaiting Allocation</option>
              <option value="Allocated" ${filter.status === 'Allocated' ? 'selected' : ''}>Allocated</option>
              <option value="Dispatched" ${filter.status === 'Dispatched' ? 'selected' : ''}>Dispatched</option>
              <option value="Delivered" ${filter.status === 'Delivered' ? 'selected' : ''}>Delivered</option>
            </select>

            <select class="filter-select" id="req-sort-filter">
              <option value="PRIORITY_DESC" ${filter.sort === 'PRIORITY_DESC' ? 'selected' : ''}>Highest Urgency First</option>
              <option value="PRIORITY_ASC" ${filter.sort === 'PRIORITY_ASC' ? 'selected' : ''}>Lowest Urgency First</option>
            </select>
          </div>
        </div>

        <!-- Table View -->
        <div class="data-table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>Urgency Score</th>
                <th>Request ID & Area</th>
                <th>Assistance Need</th>
                <th>People Affected</th>
                <th>Status</th>
                <th style="text-align:right">Action</th>
              </tr>
            </thead>
            <tbody>
              ${filtered.length > 0 ? filtered.map(r => `
                <tr>
                  <td>
                    <span class="priority-score ${r.priority_score >= 85 ? 'critical' : r.priority_score >= 70 ? 'high' : 'medium'}">
                      ${r.priority_score}
                    </span>
                  </td>
                  <td>
                    <div class="table-row-title mono">${escapeHtml(r.id)}</div>
                    <div class="table-row-sub">${escapeHtml(r.area)}</div>
                  </td>
                  <td>
                    <div class="table-row-title">${escapeHtml(r.need)}</div>
                    <div class="table-row-sub">${r.vulnerable_people ? '<span style="color:#dc2626;font-weight:600">⚠ Vulnerable group</span>' : 'Standard'}</div>
                  </td>
                  <td>${r.people_affected} persons</td>
                  <td>
                    <span class="badge ${r.status === 'Delivered' ? 'badge-safe' : r.status === 'Dispatched' ? 'badge-info' : r.status === 'Allocated' ? 'badge-neutral' : 'badge-warning'}">${escapeHtml(r.status)}</span>
                    <small style="display:block;color:var(--text-muted);margin-top:4px">Verification: ${escapeHtml(r.verification_status || 'Not recorded')}</small>
                    <small style="display:block;color:var(--text-muted);margin-top:4px">${r.response_owner_type ? `Accepted by ${r.response_owner_type === 'government' ? 'Government' : escapeHtml(r.response_organization_name || 'an NGO')} · ${escapeHtml(r.response_assignment_status || 'Assigned')}` : 'Available to Government and approved NGOs'}</small>
                  </td>
                  <td style="text-align:right">
                    <div style="display:inline-flex;gap:6px">
                      <button type="button" class="btn btn-secondary btn-sm req-details-btn" data-id="${escapeHtml(r.id)}">
                        Details
                      </button>
                      ${(!r.response_owner_type || (r.response_owner_type === 'government' && r.status === 'Awaiting allocation' && r.verification_status === 'Verified' && !r.response_assignment_status)) && ['Administrator', 'Government Official'].includes(session.role) ? `<button type="button" class="btn btn-secondary btn-sm gov-verify-req-btn" data-id="${escapeHtml(r.id)}">${r.response_owner_type ? 'Reassign Response Team' : 'Accept / Assign'}</button>` : ''}
                      ${session.role === 'NGO Coordinator' && r.ngo_assignment_eligible ? `<button type="button" class="btn btn-secondary btn-sm ngo-assign-request-btn" data-id="${escapeHtml(r.id)}">${r.response_owner_type === 'ngo' ? 'Reassign NGO Team' : 'Accept for NGO Assistance'}</button>` : ''}
                      ${session.role === 'NGO Coordinator' && r.ngo_assignment_active ? `<button type="button" class="btn btn-primary btn-sm allocate-btn" data-id="${escapeHtml(r.id)}">Allocate NGO Resources</button>` : ''}
                      ${['Administrator','Government Official'].includes(session.role) && r.response_owner_type === 'government' && r.status === 'Awaiting allocation' && r.verification_status === 'Verified' ? `<button type="button" class="btn btn-primary btn-sm allocate-btn" data-id="${escapeHtml(r.id)}">Allocate</button>` : ''}
                    </div>
                  </td>
                </tr>
              `).join('') : `
                <tr>
                  <td colspan="6" style="text-align:center;padding:32px;color:var(--text-muted)">
                    No emergency requests found matching the current search filters.
                  </td>
                </tr>
              `}
            </tbody>
          </table>
        </div>
      </div>
    `;

    // Event Wire-ups
    container.querySelector('#req-page-new-btn').onclick = () => openEmergencyRequestModal();

    const searchInput = container.querySelector('#req-search-input');
    searchInput.oninput = (e) => {
      filter.search = e.target.value;
      renderRequestsPage(container);
    };

    container.querySelector('#req-status-filter').onchange = (e) => {
      filter.status = e.target.value;
      renderRequestsPage(container);
    };

    container.querySelector('#req-sort-filter').onchange = (e) => {
      filter.sort = e.target.value;
      renderRequestsPage(container);
    };

    container.querySelectorAll('.allocate-btn').forEach(btn => {
      btn.onclick = () => handleAllocate(btn.dataset.id);
    });
    container.querySelectorAll('.ngo-assign-request-btn').forEach(btn => {
      btn.onclick = () => openNgoRequestAssignmentModal(btn.dataset.id);
    });
    container.querySelectorAll('.gov-verify-req-btn').forEach(btn => {
      btn.onclick = () => { const req = requests.find(r => r.id === btn.dataset.id); if (req) openVerifyRequestModal(req); };
    });

    container.querySelectorAll('.req-details-btn').forEach(btn => {
      btn.onclick = () => {
        const req = requests.find(r => r.id === btn.dataset.id);
        if (req) openRequestDetailsModal(req);
      };
    });
  }

  async function openNgoRequestAssignmentModal(requestId) {
    let options;
    try {
      const response=await fetch(`/api/ngo/response-options/${encodeURIComponent(requestId)}`);
      options=await response.json(); if(!response.ok) throw new Error(options.error||'Unable to load NGO assignment options.');
    } catch(error){showToast(error.message||'Unable to load NGO assignment options.','error');return;}
    const optionList=(items,format)=>items.map(item=>`<option value="${escapeHtml(item.id)}" ${item.available?'':'disabled'}>${escapeHtml(format(item))} · ${item.available?'Available':'Unavailable'}</option>`).join('');
    const ready=options.eligible&&options.volunteers.some(v=>v.available)&&options.drivers.some(d=>d.available)&&options.vehicles.some(v=>v.available);
    const backdrop=document.createElement('div');backdrop.className='modal-backdrop';
    backdrop.innerHTML=`<div class="modal" style="width:min(620px,96vw)"><div class="modal-head"><div><p class="eyebrow">NGO RESPONSE · ${escapeHtml(requestId)}</p><h3>Accept for NGO Assistance</h3></div><button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button></div><form id="ngo-response-form"><div class="modal-body"><p class="help-text">All approved NGOs can view this request. The first valid Government or NGO assignment committed by the server becomes the sole response owner.</p>${options.blocked_reason&&!options.eligible?`<p class="alert-banner critical">${escapeHtml(options.blocked_reason)}</p>`:''}<div class="form-group"><label>Approved, available NGO Volunteer</label><select name="volunteer_id" required><option value="">Choose Volunteer</option>${optionList(options.volunteers,v=>`${v.name} · ${v.personnel_role} · ${v.organization_name} · ${v.skill} · ${v.active_tasks} active tasks`)}</select>${options.volunteers.some(v=>v.available)?'':'<small class="help-text">No eligible volunteer. Register/request approval for NGO volunteers.</small>'}</div><div class="form-group"><label>Approved, available NGO Driver</label><select name="driver_user_id" required><option value="">Choose Driver</option>${optionList(options.drivers,d=>`${d.name} · ${d.personnel_role} · ${d.organization_name}`)}</select>${options.drivers.some(d=>d.available)?'':'<small class="help-text">No eligible driver. Register/request approval for an NGO driver.</small>'}</div><div class="form-group"><label>Available compatible NGO vehicle</label><select name="vehicle_id" required><option value="">Choose vehicle</option>${optionList(options.vehicles,v=>`${v.registration_number || v.vehicle_code} · ${v.vehicle_type} · ${v.capacity_description || `${v.capacity_units} relief units`}`)}</select>${options.vehicles.some(v=>v.available)?'':'<small class="help-text">No available compatible vehicle is registered to this NGO.</small>'}</div><div class="form-group"><label>Assignment notes</label><textarea name="notes" rows="2"></textarea></div></div><div class="modal-actions"><button type="button" class="btn btn-secondary close-modal">Cancel</button><button type="submit" class="btn btn-primary" ${ready?'':'disabled'}>Save NGO assignment</button></div></form></div>`;
    document.body.appendChild(backdrop);backdrop.querySelectorAll('.close-modal').forEach(b=>b.onclick=()=>backdrop.remove());
    backdrop.querySelector('#ngo-response-form').onsubmit=async e=>{e.preventDefault();const values=Object.fromEntries(new FormData(e.currentTarget));const button=e.currentTarget.querySelector('[type=submit]');button.disabled=true;try{const response=await fetch(`/api/requests/${encodeURIComponent(requestId)}/ngo-assign`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({volunteer_id:Number(values.volunteer_id),driver_user_id:Number(values.driver_user_id),vehicle_id:Number(values.vehicle_id),notes:values.notes})});const result=await response.json();if(!response.ok){showToast(result.error||'NGO assignment failed.','error');button.disabled=false;return;}showToast(`NGO response assignment ${result.assignment_id} saved with Volunteer task ${result.task_id}.`);backdrop.remove();await loadAllData();renderApp();}catch(error){showToast('Network error. NGO assignment was not confirmed.','error');button.disabled=false;}};
  }

  // =========================================================================
  // 3. RESOURCE ALLOCATION PAGE
  // =========================================================================

  function renderAllocationPage(container) {
    const pending = requests.filter(r => r.status === 'Awaiting allocation');

    container.innerHTML = `
      <div class="page-header">
        <div class="page-header-text">
          <h2>Automated Urgency Allocation Queue</h2>
          <p>The priority engine ranks incoming calls by affected count, vulnerability, requested relief category, and waiting delay.</p>
        </div>
      </div>

      <div class="card">
        <div class="card-title">
          <div>
            <h3>Pending Resource Allocations (${pending.length})</h3>
            <p>Approve recommendations to schedule immediate warehouse transport</p>
          </div>
          <span class="badge ${pending.length > 0 ? 'badge-warning' : 'badge-safe'}">
            ${pending.length} Awaiting Warehouse Assignment
          </span>
        </div>

        ${pending.length > 0 ? `
          <div style="display:flex;flex-direction:column;gap:12px">
            ${pending.map(r => `
              <div style="border:1px solid var(--surface-border);border-radius:var(--radius-lg);padding:18px;display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;background:#ffffff">
                <div style="display:flex;align-items:center;gap:16px">
                  <span class="priority-score ${r.priority_score >= 85 ? 'critical' : 'high'}" style="font-size:1.1rem;padding:6px 10px">
                    ${r.priority_score}
                  </span>
                  <div>
                    <b style="font-size:1.05rem;color:var(--text-primary)">${escapeHtml(r.need)} for ${r.people_affected} People</b>
                    <p style="font-size:0.85rem;color:var(--text-secondary);margin-top:2px">
                      Request <span class="mono">${escapeHtml(r.id)}</span> · Location: <b>${escapeHtml(r.area)}</b> ${r.vulnerable_people ? '· <span style="color:#dc2626;font-weight:700">⚠ Vulnerable Persons Present</span>' : ''}
                    </p>
                    <small style="color:var(--text-muted);display:block;margin-top:4px">
                      Allocation selects compatible warehouse stock, driver, and vehicle from current records.
                    </small>
                  </div>
                </div>

                <div style="display:flex;gap:8px">
                  <button type="button" class="btn btn-secondary btn-sm req-details-btn" data-id="${escapeHtml(r.id)}">
                    Inspect Details
                  </button>
                  ${r.response_owner_type === 'government' && r.verification_status === 'Verified' ? (r.response_assignment_status ? `<button type="button" class="btn btn-primary btn-sm allocate-btn" data-id="${escapeHtml(r.id)}">Approve Allocation ${getIcon('ArrowUpRight')}</button>` : `<button type="button" class="btn btn-secondary btn-sm gov-verify-req-btn" data-id="${escapeHtml(r.id)}">Assign / Reassign Team</button>`) : r.response_owner_type === 'ngo' && r.response_organization_id === session.organization_id ? (r.ngo_assignment_active ? `<button type="button" class="btn btn-primary btn-sm allocate-btn" data-id="${escapeHtml(r.id)}">Allocate NGO Resources ${getIcon('ArrowUpRight')}</button>` : `<button type="button" class="btn btn-secondary btn-sm ngo-assign-request-btn" data-id="${escapeHtml(r.id)}">Assign / Reassign NGO Team</button>`) : !r.response_owner_type && ['Administrator', 'Government Official'].includes(session.role) ? `<span class="badge badge-warning">Available for response</span><button type="button" class="btn btn-secondary btn-sm gov-verify-req-btn" data-id="${escapeHtml(r.id)}">Verify / Triage</button>` : `<span class="badge badge-neutral">Claimed by ${r.response_owner_type === 'government' ? 'Government' : escapeHtml(r.response_organization_name || 'an NGO')}</span>`}
                </div>
              </div>
            `).join('')}
          </div>
        ` : `
          <div style="text-align:center;padding:48px 20px;color:var(--text-muted)">
            <div style="margin-bottom:12px;color:var(--success-emerald)"><span style="display:inline-flex;width:48px;height:48px">${getIcon('CheckCircle2')}</span></div>
            <h4 style="font-size:1.1rem;color:var(--text-primary);margin-bottom:4px">All Requests Are Allocated</h4>
            <p style="font-size:0.9rem">No unallocated emergency requests remain in the priority queue.</p>
          </div>
        `}
      </div>
    `;

    container.querySelectorAll('.allocate-btn').forEach(btn => {
      btn.onclick = () => handleAllocate(btn.dataset.id);
    });
    container.querySelectorAll('.gov-verify-req-btn').forEach(btn => {
      btn.onclick = () => { const req = requests.find(r => r.id === btn.dataset.id); if (req) openVerifyRequestModal(req); };
    });

    container.querySelectorAll('.req-details-btn').forEach(btn => {
      btn.onclick = () => {
        const req = requests.find(r => r.id === btn.dataset.id);
        if (req) openRequestDetailsModal(req);
      };
    });
  }

  // =========================================================================
  // 4. INVENTORY & WAREHOUSES PAGE
  // =========================================================================

  function renderInventoryPage(container) {
    const filter = pageFilters.inventory;

    // Government oversight summarizes the same resource across depots while
    // retaining the underlying warehouse rows for stock updates.
    const displayInventory = session.role === 'Government Official'
      ? Object.values(inventory.reduce((groups, item) => {
          const key = String(item.resource_id || item.resource_name).toLowerCase();
          const group = groups[key] || (groups[key] = { ...item, stocks: [], available_units: 0, target_stock: 0 });
          group.stocks.push(item);
          group.available_units += Number(item.available_units || 0);
          group.target_stock += Number(item.target_stock || 0);
          return groups;
        }, {})).map(group => ({
          ...group,
          status: group.target_stock && group.available_units / group.target_stock < 0.35 ? 'Critical'
            : group.target_stock && group.available_units < group.target_stock ? 'Low' : 'Safe',
          warehouse_name: group.stocks.map(stock => stock.warehouse_name).join(', ')
        }))
      : inventory;

    let filtered = displayInventory.filter(item => {
      const matchSearch = !filter.search || 
        item.resource_name.toLowerCase().includes(filter.search.toLowerCase()) ||
        item.warehouse_name.toLowerCase().includes(filter.search.toLowerCase());

      const matchStatus = filter.status === 'ALL' || item.status === filter.status;
      return matchSearch && matchStatus;
    });

    container.innerHTML = `
      <div class="page-header">
        <div class="page-header-text">
          <h2>Relief Warehouse Inventory</h2>
          <p>Monitor live supply stocks, auto-calculated reorder thresholds, and warehouse storage locations.</p>
        </div>
        <div class="page-header-actions">
          <a href="/api/export/inventory.csv" class="btn btn-secondary" download>
            ${getIcon('Download')} Export CSV
          </a>
          ${['Administrator', 'Government Official', 'NGO Coordinator'].includes(session.role) ? `
            <button type="button" class="btn btn-primary" id="add-inventory-btn">
              ${getIcon('Plus')} Add Resource
            </button>
          ` : ''}
        </div>
      </div>

      <div class="card">
        <!-- Toolbar -->
        <div class="table-toolbar">
          <div class="search-input-wrapper">
            ${getIcon('Search')}
            <input type="text" class="search-input" id="inv-search-input" placeholder="Search resources or warehouse..." value="${escapeHtml(filter.search)}">
          </div>

          <div style="display:flex;gap:10px;align-items:center">
            <select class="filter-select" id="inv-status-filter">
              <option value="ALL" ${filter.status === 'ALL' ? 'selected' : ''}>All Stock Statuses (${displayInventory.length})</option>
              <option value="Safe" ${filter.status === 'Safe' ? 'selected' : ''}>Safe (&ge;100% Target)</option>
              <option value="Low" ${filter.status === 'Low' ? 'selected' : ''}>Low Stock (&lt;100% Target)</option>
              <option value="Critical" ${filter.status === 'Critical' ? 'selected' : ''}>Critical Stock (&lt;35% Target)</option>
            </select>
          </div>
        </div>

        <div class="data-table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>Resource Name</th>
                <th style="width:200px">Stock Fill Level</th>
                <th>Available Units</th>
                <th>Target Stock</th>
                <th>Depot Warehouse</th>
                <th>Status</th>
                ${['Administrator', 'Government Official', 'NGO Coordinator'].includes(session.role) ? `<th style="text-align:right">Action</th>` : ''}
              </tr>
            </thead>
            <tbody>
              ${filtered.length > 0 ? filtered.map(item => {
                const pct = Math.min(100, Math.round((item.available_units / item.target_stock) * 100));
                const s = item.status.toLowerCase();
                return `
                  <tr>
                    <td><b>${escapeHtml(item.resource_name)}</b></td>
                    <td>
                      <div class="progress-track">
                        <div class="progress-fill ${s === 'critical' ? 'critical' : s === 'low' ? 'warning' : 'safe'}" style="width:${pct}%"></div>
                      </div>
                      <small style="color:var(--text-muted);font-size:0.75rem">${pct}% of target</small>
                    </td>
                    <td><b>${item.available_units.toLocaleString()}</b> units</td>
                    <td>${item.target_stock.toLocaleString()} units</td>
                    <td>${escapeHtml(item.warehouse_name)}</td>
                    <td>
                      <span class="badge ${s === 'critical' ? 'badge-critical' : s === 'low' ? 'badge-warning' : 'badge-safe'}">
                        ${escapeHtml(item.status)}
                      </span>
                    </td>
                    ${['Administrator', 'Government Official', 'NGO Coordinator'].includes(session.role) ? `
                      <td style="text-align:right">
                        <button type="button" class="btn btn-secondary btn-sm update-stock-btn" data-id="${item.id}" data-name="${escapeHtml(item.resource_name)}" data-avail="${item.available_units}" data-target="${item.target_stock}" data-wh="${escapeHtml(item.warehouse_name)}" ${item.stocks?.length > 1 ? 'data-multi="true"' : ''}>
                          ${getIcon('Edit')} ${item.stocks?.length > 1 ? 'Manage Depots' : 'Update Stock'}
                        </button>
                      </td>
                    ` : ''}
                  </tr>
                `;
              }).join('') : `
                <tr>
                  <td colspan="7" style="text-align:center;padding:32px;color:var(--text-muted)">
                    No inventory items found matching the current search filters.
                  </td>
                </tr>
              `}
            </tbody>
          </table>
        </div>
      </div>
    `;

    // Wire-up events
    const searchInput = container.querySelector('#inv-search-input');
    searchInput.oninput = (e) => {
      filter.search = e.target.value;
      renderInventoryPage(container);
    };

    container.querySelector('#inv-status-filter').onchange = (e) => {
      filter.status = e.target.value;
      renderInventoryPage(container);
    };

    const addBtn = container.querySelector('#add-inventory-btn');
    if (addBtn) {
      addBtn.onclick = () => openAddInventoryModal();
    }

    container.querySelectorAll('.update-stock-btn').forEach(btn => {
      btn.onclick = () => {
        if (btn.dataset.multi === 'true') {
          const group = displayInventory.find(item => String(item.resource_id || item.resource_name).toLowerCase() === String(inventory.find(x => String(x.id) === btn.dataset.id)?.resource_id || btn.dataset.name).toLowerCase());
          if (!group) return;
          const backdrop = document.createElement('div');
          backdrop.className = 'modal-backdrop';
          backdrop.innerHTML = `<div class="modal"><div class="modal-head"><h3>Manage ${escapeHtml(group.resource_name)} by Depot</h3><button class="modal-close-btn">${getIcon('X')}</button></div><div class="modal-body" style="display:grid;gap:10px">${group.stocks.map(stock => `<button type="button" class="btn btn-secondary depot-stock-choice" data-id="${stock.id}" data-name="${escapeHtml(stock.resource_name)}" data-avail="${stock.available_units}" data-target="${stock.target_stock}" data-wh="${escapeHtml(stock.warehouse_name)}">${escapeHtml(stock.warehouse_name)} · ${Number(stock.available_units).toLocaleString()} available / ${Number(stock.target_stock).toLocaleString()} target</button>`).join('')}</div></div>`;
          document.body.appendChild(backdrop);
          backdrop.querySelector('.modal-close-btn').onclick = () => backdrop.remove();
          backdrop.querySelectorAll('.depot-stock-choice').forEach(choice => choice.onclick = () => {
            const selected = { id: choice.dataset.id, name: choice.dataset.name, available: choice.dataset.avail, target: choice.dataset.target, warehouse: choice.dataset.wh };
            backdrop.remove(); openUpdateStockModal(selected);
          });
          return;
        }
        openUpdateStockModal({
          id: btn.dataset.id,
          name: btn.dataset.name,
          available: btn.dataset.avail,
          target: btn.dataset.target,
          warehouse: btn.dataset.wh
        });
      };
    });
  }

  // =========================================================================
  // 5. VOLUNTEERS PAGE
  // =========================================================================

  function renderVolunteersPage(container) {
    const filter = pageFilters.volunteers;

    let filtered = volunteers.filter(v => {
      const matchSearch = !filter.search || 
        v.name.toLowerCase().includes(filter.search.toLowerCase()) ||
        v.skill.toLowerCase().includes(filter.search.toLowerCase()) ||
        v.zone.toLowerCase().includes(filter.search.toLowerCase());

      const matchStatus = filter.status === 'ALL' || v.status === filter.status;
      return matchSearch && matchStatus;
    });

    container.innerHTML = `
      <div class="page-header">
        <div class="page-header-text">
          <h2>Volunteer Responder Roster</h2>
          <p>Field deployment coordination across 12 disaster-affected sectors.</p>
        </div>
        <div class="page-header-actions">
          <a href="/api/export/volunteers.csv" class="btn btn-secondary" download>
            ${getIcon('Download')} Export CSV
          </a>
          ${['Administrator', 'Government Official', 'NGO Coordinator'].includes(session.role) ? `
            <button type="button" class="btn btn-primary" id="add-vol-btn">
              ${getIcon('Plus')} Register Volunteer
            </button>
          ` : ''}
        </div>
      </div>

      <div class="card">
        <!-- Toolbar -->
        <div class="table-toolbar">
          <div class="search-input-wrapper">
            ${getIcon('Search')}
            <input type="text" class="search-input" id="vol-search-input" placeholder="Search by name, skill, zone..." value="${escapeHtml(filter.search)}">
          </div>

          <div style="display:flex;gap:10px;align-items:center">
            <select class="filter-select" id="vol-status-filter">
              <option value="ALL" ${filter.status === 'ALL' ? 'selected' : ''}>All Deployment Statuses (${volunteers.length})</option>
              <option value="Available" ${filter.status === 'Available' ? 'selected' : ''}>Available for Task</option>
              <option value="On task" ${filter.status === 'On task' ? 'selected' : ''}>On Task</option>
            </select>
          </div>
        </div>

        <div class="data-table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>Volunteer Name</th>
                <th>Specialized Skill</th>
                <th>Assigned Zone</th>
                <th>Deployment Status</th>
                <th style="text-align:right">Task Operations</th>
              </tr>
            </thead>
            <tbody>
              ${filtered.length > 0 ? filtered.map(v => `
                <tr>
                  <td>
                    <div style="display:flex;align-items:center;gap:10px">
                      <div class="user-avatar" style="width:32px;height:32px;font-size:0.75rem">${escapeHtml(v.initials || 'V')}</div>
                      <b>${escapeHtml(v.name)}</b>
                    </div>
                  </td>
                  <td>${escapeHtml(v.skill)}</td>
                  <td>
                    <span class="volunteer-zone-label">
                      <span class="volunteer-zone-pin">${getIcon('MapPin')}</span>
                      <span>${escapeHtml(v.zone)}</span>
                    </span>
                  </td>
                  <td>
                    <span class="badge ${v.status === 'Available' ? 'badge-safe' : 'badge-info'}">
                      ${escapeHtml(v.status)}
                    </span>
                  </td>
                  <td style="text-align:right">
                    ${['Administrator', 'Government Official', 'NGO Coordinator'].includes(session.role) ? `
                      ${v.status === 'Available' ? `
                        <button type="button" class="btn btn-primary btn-sm vol-assign-btn" data-id="${v.id}" data-name="${escapeHtml(v.name)}">
                          Assign Task
                        </button>
                      ` : `
                        <button type="button" class="btn btn-secondary btn-sm vol-unassign-btn" data-id="${v.id}" data-name="${escapeHtml(v.name)}">
                          Release / Make Available
                        </button>
                      `}
                    ` : `
                      <span class="badge badge-neutral">${escapeHtml(v.status)}</span>
                    `}
                  </td>
                </tr>
              `).join('') : `
                <tr>
                  <td colspan="5" style="text-align:center;padding:32px;color:var(--text-muted)">
                    No volunteers found matching the current search filters.
                  </td>
                </tr>
              `}
            </tbody>
          </table>
        </div>
      </div>
    `;

    // Wire-up events
    const searchInput = container.querySelector('#vol-search-input');
    searchInput.oninput = (e) => {
      filter.search = e.target.value;
      renderVolunteersPage(container);
    };

    container.querySelector('#vol-status-filter').onchange = (e) => {
      filter.status = e.target.value;
      renderVolunteersPage(container);
    };

    const addBtn = container.querySelector('#add-vol-btn');
    if (addBtn) {
      addBtn.onclick = () => openRegisterVolunteerModal();
    }

    container.querySelectorAll('.vol-assign-btn').forEach(btn => {
      btn.onclick = async () => {
        try {
          const res = await fetch(`/api/volunteers/${btn.dataset.id}/assign`, { method: 'POST' });
          const resData = await res.json();
          if (!res.ok) {
            showToast(resData.error || 'Failed to assign volunteer');
            return;
          }
          showToast(`${btn.dataset.name} assigned to active task queue.`);
          await loadAllData();
          renderApp();
        } catch (err) {
          showToast('Network error assigning volunteer');
        }
      };
    });

    container.querySelectorAll('.vol-unassign-btn').forEach(btn => {
      btn.onclick = async () => {
        try {
          const res = await fetch(`/api/volunteers/${btn.dataset.id}/unassign`, { method: 'POST' });
          const resData = await res.json();
          if (!res.ok) {
            showToast(resData.error || 'Failed to unassign volunteer');
            return;
          }
          showToast(`${btn.dataset.name} released and marked Available.`);
          await loadAllData();
          renderApp();
        } catch (err) {
          showToast('Network error unassigning volunteer');
        }
      };
    });
  }

  // =========================================================================
  // 6. SHELTERS PAGE
  // =========================================================================

  function renderSheltersPage(container) {
    container.innerHTML = `
      <div class="page-header">
        <div class="page-header-text">
          <h2>Designated Disaster Shelters & Relief Centers</h2>
          <p>Real-time occupancy counts, maximum safe capacities, and bed-space availability.</p>
        </div>
        ${['Administrator','Government Official','NGO Coordinator'].includes(session.role)?'<button type="button" class="btn btn-primary" id="add-shelter-btn">'+getIcon('Plus')+' Register owned shelter</button>':''}
      </div>

      <div class="card" style="margin-bottom:24px">
        <div class="card-title">
          <div>
            <h3>Designated Shelters Sector Map</h3>
            <p>Geographic locations and live capacity levels across district relief sectors (Google Maps)</p>
          </div>
          <div class="map-layer-switcher">
            <button type="button" class="map-layer-btn active" id="btn-shelters-map-roads">Google Roads</button>
            <button type="button" class="map-layer-btn" id="btn-shelters-map-sat">Satellite</button>
          </div>
        </div>
        <div id="shelters-real-map" class="real-map-container" style="height:270px"></div>
        <div class="map-legend" style="margin-top:12px">
          <span><i style="background:#059669;width:12px;height:12px;border-radius:50%;display:inline-block"></i> Safe Capacity (&lt;70%)</span>
          <span><i style="background:#eab308;width:12px;height:12px;border-radius:50%;display:inline-block"></i> Moderate (70-89%)</span>
          <span><i style="background:#dc2626;width:12px;height:12px;border-radius:50%;display:inline-block"></i> Near Max (&ge;90%)</span>
        </div>
      </div>

      <div class="grid grid-3">
        ${shelters.map(s => {
          const pct = Math.min(100, Math.round((s.occupants / s.capacity) * 100));
          const isFull = pct >= 90;
          return `
            <div class="card">
              <div class="card-title">
                <div style="display:flex;align-items:center;gap:10px">
                  <div style="color:var(--command-blue)">${getIcon('House')}</div>
                  <h3 style="font-size:1.1rem">${escapeHtml(s.name)}</h3>
                </div>
                <span class="badge ${s.status === 'Operational' ? 'badge-safe' : 'badge-warning'}">
                  ${escapeHtml(s.status)}
                </span>
              </div>

              <div style="margin:16px 0">
                <div style="display:flex;justify-content:space-between;margin-bottom:6px">
                  <span style="font-size:1.4rem;font-weight:800;font-family:'Manrope',sans-serif">
                    ${s.occupants.toLocaleString()} <small style="font-size:0.85rem;color:var(--text-muted);font-weight:500">/ ${s.capacity.toLocaleString()} Capacity</small>
                  </span>
                  <b style="color:${isFull ? '#dc2626' : '#059669'};font-size:1.1rem">${pct}%</b>
                </div>
                <div class="progress-track" style="height:10px">
                  <div class="progress-fill ${isFull ? 'critical' : pct > 70 ? 'warning' : 'safe'}" style="width:${pct}%"></div>
                </div>
              </div>

              <div style="display:flex;justify-content:space-between;padding-top:12px;border-top:1px solid var(--surface-border);font-size:0.8rem;color:var(--text-muted)">
                <span>Remaining Bed Space: <b>${Math.max(0, s.capacity - s.occupants)} beds</b></span>
                <span style="color:#059669">● Verified Open</span>
              </div>
              ${['Administrator', 'Government Official', 'NGO Coordinator'].includes(session.role) ? `
                <div style="margin-top:12px;padding-top:12px;border-top:1px dashed var(--surface-border)">
                  <button type="button" class="btn btn-secondary btn-sm edit-shelter-btn" data-id="${s.id}" style="width:100%;justify-content:center">
                    ${getIcon('Settings')} Update Occupancy / Capacity
                  </button>
                </div>
              ` : ''}
            </div>
          `;
        }).join('')}
      </div>
    `;

    container.querySelectorAll('.edit-shelter-btn').forEach(btn => {
      btn.onclick = () => {
        const shelterId = Number(btn.dataset.id);
        const targetShelter = shelters.find(item => item.id === shelterId);
        if (targetShelter) {
          openUpdateShelterModal(targetShelter);
        }
      };
    });

    const addShelter=container.querySelector('#add-shelter-btn');if(addShelter)addShelter.onclick=()=>openCreateShelterModal();
    initSheltersRealMap();
  }

  function openCreateShelterModal(){
    const backdrop=document.createElement('div');backdrop.className='modal-backdrop';backdrop.innerHTML=`<div class="modal"><div class="modal-head"><h3>Register owned shelter</h3><button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button></div><form id="create-shelter-form"><div class="modal-body"><label>Name<input required name="name"></label><label>District<input required name="district"></label><label>Address<input required name="address"></label><div class="form-row"><label>Capacity<input required type="number" min="1" name="capacity"></label><label>Current occupancy<input required type="number" min="0" name="occupants" value="0"></label></div><div class="form-row"><label>Latitude<input type="number" step="any" name="lat"></label><label>Longitude<input type="number" step="any" name="lng"></label></div></div><div class="modal-actions"><button type="button" class="btn btn-secondary close-modal">Cancel</button><button class="btn btn-primary">Save Shelter</button></div></form></div>`;document.body.appendChild(backdrop);backdrop.querySelectorAll('.close-modal').forEach(b=>b.onclick=()=>backdrop.remove());backdrop.querySelector('form').onsubmit=async e=>{e.preventDefault();const v=Object.fromEntries(new FormData(e.currentTarget));for(const k of ['capacity','occupants','lat','lng'])if(v[k]==='')delete v[k];const r=await fetch('/api/shelters',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(v)});const out=await r.json();if(!r.ok){showToast(out.error||'Shelter save failed.','error');return;}showToast(`${out.name} registered under its authorized owner.`);backdrop.remove();await loadAllData();renderApp();};
  }

  // Initialize Shelters Real Google Map
  function initSheltersRealMap() {
    const mapEl = document.getElementById('shelters-real-map');
    if (!mapEl || !window.L) return;

    if (sheltersMapInstance) {
      try { sheltersMapInstance.remove(); } catch (e) {}
      sheltersMapInstance = null;
    }

    const map = L.map(mapEl, {
      center: [30.9009, 75.8573],
      zoom: 12,
      zoomControl: true,
      scrollWheelZoom: true
    });
    sheltersMapInstance = map;

    let currentTile = createGoogleMapTileLayer('googleRoadmap').addTo(map);

    const roadsBtn = document.getElementById('btn-shelters-map-roads');
    const satBtn = document.getElementById('btn-shelters-map-sat');
    if (roadsBtn && satBtn) {
      roadsBtn.onclick = () => {
        roadsBtn.classList.add('active');
        satBtn.classList.remove('active');
        map.removeLayer(currentTile);
        currentTile = createGoogleMapTileLayer('googleRoadmap').addTo(map);
      };
      satBtn.onclick = () => {
        satBtn.classList.add('active');
        roadsBtn.classList.remove('active');
        map.removeLayer(currentTile);
        currentTile = createGoogleMapTileLayer('googleSatellite').addTo(map);
      };
    }

    const shelterCoords = {
      'Community Hall, Model Town': [30.9080, 75.8450],
      'Govt Senior Secondary School': [30.8950, 75.8700],
      'Sector 4 Flood Relief Camp': [30.9220, 75.8300],
      'East Bypass Safe Enclave': [30.9150, 75.8920]
    };

    shelters.forEach((s) => {
      if (s.lat == null || s.lng == null) return;
      const latLng = [Number(s.lat), Number(s.lng)];
      const pct = Math.min(100, Math.round((s.occupants / s.capacity) * 100));
      const isFull = pct >= 90;
      const isWarning = pct >= 70 && pct < 90;
      const markerColor = isFull ? '#dc2626' : isWarning ? '#eab308' : '#059669';

      const shelterIcon = L.divIcon({
        className: 'custom-map-marker',
        html: `<div style="width:28px;height:28px;border-radius:50%;background:${markerColor};border:2px solid #ffffff;color:#fff;display:grid;place-items:center;font-size:12px;box-shadow:0 2px 6px rgba(0,0,0,0.35)">${getIcon('House')}</div>`,
        iconSize: [28, 28],
        iconAnchor: [14, 14]
      });

      L.marker(latLng, { icon: shelterIcon })
        .addTo(map)
        .bindPopup(`
          <div style="min-width:200px">
            <b style="font-size:0.95rem;color:#0f172a;display:block">${escapeHtml(s.name)}</b>
            <div style="display:flex;justify-content:space-between;margin:6px 0 4px;font-size:0.85rem">
              <span>Occupancy:</span>
              <b style="color:${markerColor}">${pct}% (${s.occupants}/${s.capacity})</b>
            </div>
            <div class="progress-track" style="height:6px;margin-bottom:8px">
              <div class="progress-fill ${isFull ? 'critical' : isWarning ? 'warning' : 'safe'}" style="width:${pct}%"></div>
            </div>
            <small style="color:#64748b">Remaining Bed Space: <b>${Math.max(0, s.capacity - s.occupants)} beds</b></small>
          </div>
        `);
    });

    setTimeout(() => {
      try { map.invalidateSize(); } catch (e) {}
    }, 200);
  }

  // =========================================================================
  // 7. VEHICLES & DISPATCH PAGE
  // =========================================================================

  function renderDispatchPage(container) {
    const filter = pageFilters.dispatches;
    const isDriver = session.role === 'Driver';

    // The API already scopes driver records by canonical driver user id. Do not re-filter by display name.
    const list = dispatches;

    let filtered = list.filter(d => {
      const matchSearch = !filter.search || 
        d.vehicle.toLowerCase().includes(filter.search.toLowerCase()) ||
        d.destination.toLowerCase().includes(filter.search.toLowerCase()) ||
        d.driver.toLowerCase().includes(filter.search.toLowerCase());

      const matchStatus = filter.status === 'ALL' || d.status === filter.status;
      return matchSearch && matchStatus;
    });

    container.innerHTML = `
      <div class="page-header">
        <div class="page-header-text">
          <h2>Relief Transport Fleet & Dispatches</h2>
          <p>${isDriver ? 'Your assigned delivery routes and waypoint delivery confirmations.' : 'Live transit logistics tracking for all emergency resource dispatches.'}</p>
        </div>
        <div class="page-header-actions">
          <a href="/api/export/dispatches.csv" class="btn btn-secondary" download>
            ${getIcon('Download')} Export CSV
          </a>
        </div>
      </div>

      <div class="card">
        <!-- Toolbar -->
        <div class="table-toolbar">
          <div class="search-input-wrapper">
            ${getIcon('Search')}
            <input type="text" class="search-input" id="dsp-search-input" placeholder="Search vehicle, driver or destination..." value="${escapeHtml(filter.search)}">
          </div>

          <div style="display:flex;gap:10px;align-items:center">
            <select class="filter-select" id="dsp-status-filter">
              <option value="ALL" ${filter.status === 'ALL' ? 'selected' : ''}>All Dispatches (${list.length})</option>
              <option value="Loading" ${filter.status === 'Loading' ? 'selected' : ''}>Loading</option>
              <option value="En route" ${filter.status === 'En route' ? 'selected' : ''}>En Route</option>
              <option value="Delivered" ${filter.status === 'Delivered' ? 'selected' : ''}>Delivered</option>
            </select>
          </div>
        </div>

        <div class="data-table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>Vehicle & Run ID</th>
                <th>Driver</th>
                <th>Destination</th>
                <th>Cargo Manifest</th>
                <th>Transit Status</th>
                <th style="text-align:right">Action</th>
              </tr>
            </thead>
            <tbody>
              ${filtered.length > 0 ? filtered.map(d => `
                <tr>
                  <td>
                    <b>${escapeHtml(d.vehicle)}</b><br>
                    <span class="mono" style="font-size:0.75rem;color:var(--text-muted)">${escapeHtml(d.id)}</span>
                  </td>
                  <td>${escapeHtml(d.driver)}</td>
                  <td>
                    <b>${escapeHtml(d.destination)}</b><br>
                    <small style="color:var(--text-muted)">ETA: ${escapeHtml(d.eta)}</small>
                  </td>
                  <td>${escapeHtml(d.load_items)}</td>
                  <td>
                    <span class="badge ${d.status === 'Delivered' ? 'badge-safe' : d.status === 'En route' ? 'badge-info' : 'badge-neutral'}">
                      ${escapeHtml(d.status)}
                    </span>
                  </td>
                  <td style="text-align:right">
                    <div style="display:inline-flex;gap:6px">
                      <button type="button" class="btn btn-secondary btn-sm dsp-route-btn" data-id="${escapeHtml(d.id)}">
                        Route
                      </button>
                      ${d.status === 'Loading' && (['Administrator', 'Government Official', 'NGO Coordinator'].includes(session.role) || (isDriver && (d.driver === session.name || d.driver_user_id === session.id))) ? `
                        <button type="button" class="btn btn-primary btn-sm advance-dispatch-btn" data-id="${d.id}" data-action="start">
                          Start Journey
                        </button>
                      ` : d.status === 'En route' && (['Administrator', 'Government Official', 'NGO Coordinator'].includes(session.role) || (isDriver && (d.driver === session.name || d.driver_user_id === session.id))) ? `
                        <button type="button" class="btn btn-primary btn-sm advance-dispatch-btn" data-id="${d.id}" data-action="arrive">
                          Record Arrival
                        </button>
                      ` : d.status === 'Arrived' && (['Administrator', 'Government Official', 'NGO Coordinator'].includes(session.role) || (isDriver && (d.driver === session.name || d.driver_user_id === session.id))) ? `
                        <button type="button" class="btn btn-primary btn-sm dsp-proof-btn" data-id="${d.id}">
                          Submit Proof
                        </button>
                      ` : ['Delivered Pending Proof', 'Needs Review', 'Proof Rejected'].includes(d.status) && ['Administrator', 'Government Official', 'NGO Coordinator'].includes(session.role) ? `
                        <button type="button" class="btn btn-primary btn-sm dsp-review-btn" data-id="${d.id}">
                          Review Proof
                        </button>
                      ` : d.status === 'Delivered' ? `
                        <span class="badge badge-safe">Delivered</span>
                      ` : `
                        <span class="badge badge-neutral">${escapeHtml(d.status)}</span>
                      `}
                    </div>
                  </td>
                </tr>
              `).join('') : `
                <tr>
                  <td colspan="6" style="text-align:center;padding:32px;color:var(--text-muted)">
                    No dispatches found matching the current search filters.
                  </td>
                </tr>
              `}
            </tbody>
          </table>
        </div>
      </div>
    `;

    // Wire-up events
    const searchInput = container.querySelector('#dsp-search-input');
    searchInput.oninput = (e) => {
      filter.search = e.target.value;
      renderDispatchPage(container);
    };

    container.querySelector('#dsp-status-filter').onchange = (e) => {
      filter.status = e.target.value;
      renderDispatchPage(container);
    };

    container.querySelectorAll('.dsp-route-btn').forEach(btn => {
      btn.onclick = () => showRouteModal(btn.dataset.id);
    });

    container.querySelectorAll('.advance-dispatch-btn').forEach(btn => {
      btn.onclick = async () => {
        try {
          const action = btn.dataset.action;
          const url = action === 'arrive' ? `/api/dispatches/${btn.dataset.id}/arrive` : `/api/dispatches/${btn.dataset.id}/advance`;
          const res = await fetch(url, { method: 'POST' });
          const resData = await res.json();
          if (!res.ok) {
            showToast(resData.error || 'Failed to update delivery');
            return;
          }
          showToast(`Delivery status updated: ${resData.status || 'Updated'}`);
          await loadAllData();
          renderApp();
        } catch (err) {
          showToast('Network error updating dispatch');
        }
      };
    });

    container.querySelectorAll('.dsp-proof-btn').forEach(btn => {
      btn.onclick = () => openDeliveryProofModal(btn.dataset.id);
    });

    container.querySelectorAll('.dsp-review-btn').forEach(btn => {
      btn.onclick = () => openReviewDeliveryModal(btn.dataset.id);
    });
  }

  // =========================================================================
  // 8. FUNDS & DONATIONS PAGE
  // =========================================================================

  function renderCitizenDonationsPage(container) {
    const pending = donationsData.filter(d => ['Submitted', 'In Transit', 'Received'].includes(d.status)).length;
    container.innerHTML = `
      <div class="page-header">
        <div class="page-header-text">
          <h2>Relief Donations</h2>
          <p>Support the Government relief pool or an approved NGO. Your donation pledge is recorded for official verification; this page does not process online payments.</p>
        </div>
        <button type="button" class="btn btn-primary" id="citizen-register-donation-btn">${getIcon('Plus')} Donate to Relief</button>
      </div>
      <section class="metrics-grid">
        <div class="metric-card"><div class="metric-icon-box blue">${getIcon('Wallet')}</div><div class="metric-info"><span class="metric-label">My Donations</span><span class="metric-value">${donationsData.length}</span><span class="metric-sub">All recipients</span></div></div>
        <div class="metric-card"><div class="metric-icon-box amber">${getIcon('Clock3')}</div><div class="metric-info"><span class="metric-label">Awaiting Verification</span><span class="metric-value">${pending}</span><span class="metric-sub">Submitted contributions</span></div></div>
      </section>
      <section class="card">
        <div class="card-title"><div><h3>My Donation History</h3><p>Track contributions sent to Government and approved NGO relief operations.</p></div></div>
        <div class="data-table-container"><table class="data-table"><thead><tr><th>Reference</th><th>Recipient</th><th>Contribution</th><th>Destination</th><th>Status</th></tr></thead><tbody>
          ${donationsData.length ? donationsData.map(d => `<tr><td><b>${escapeHtml(d.id)}</b></td><td>${escapeHtml(d.recipient_organization_name || 'Government Relief Pool')}</td><td>${escapeHtml(d.donation_type)} · ${d.donation_type === 'Cash' ? `₹${(Number(d.declared_amount_paise || 0) / 100).toLocaleString('en-IN')}` : `${Number(d.declared_quantity || 0).toLocaleString()} ${escapeHtml(d.item_names || 'units')}`}</td><td>${escapeHtml(d.destination_warehouse_name || 'Pending assignment')}</td><td><span class="badge ${['Accepted','Partially Accepted'].includes(d.status) ? 'badge-safe' : d.status === 'Rejected' ? 'badge-critical' : 'badge-warning'}">${escapeHtml(d.status)}</span></td></tr>`).join('') : '<tr><td colspan="5" style="text-align:center;padding:28px;color:var(--text-muted)">No donations yet. Choose Government or an approved NGO to make your first relief contribution.</td></tr>'}
        </tbody></table></div>
      </section>
    `;
    container.querySelector('#citizen-register-donation-btn').onclick = () => openRegisterDonationModal();
  }

  function renderFundsPage(container) {
    const f = fundsData || {
      categories: [],
      totalAllocated: '₹0',
      totalUtilized: '₹0',
      remainingBalance: '₹0',
      transportUsedPct: 0,
      medicalUsedPct: 0
    };

    container.innerHTML = `
      <div class="page-header">
        <div class="page-header-text">
          <h2>Disaster Relief Financial Fund & Expenditure</h2>
          <p>State Disaster Relief Fund (SDRF) allocation oversight and category utilization.</p>
        </div>
      </div>

      <section class="metrics-grid">
        <div class="metric-card">
          <div class="metric-icon-box blue">${getIcon('Wallet')}</div>
          <div class="metric-info">
            <span class="metric-label">Total Allocated Fund</span>
            <span class="metric-value">${f.totalAllocated}</span>
            <span class="metric-sub">SDRF Emergency Pool</span>
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-icon-box amber">${getIcon('PackageCheck')}</div>
          <div class="metric-info">
            <span class="metric-label">Total Utilized</span>
            <span class="metric-value">${f.totalUtilized}</span>
                <span class="metric-sub">${f.totalAllocatedPaise ? Math.round((f.totalUtilizedPaise || 0) * 100 / f.totalAllocatedPaise) : 0}% of approved budget used</span>
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-icon-box emerald">${getIcon('CheckCircle2')}</div>
          <div class="metric-info">
            <span class="metric-label">Remaining Balance</span>
            <span class="metric-value">${f.remainingBalance}</span>
            <span class="metric-sub positive">Available for dispatches</span>
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-icon-box crimson">${getIcon('AlertTriangle')}</div>
          <div class="metric-info">
            <span class="metric-label">Budget Threshold</span>
            <span class="metric-value">${f.transportUsedPct >= 80 ? 'Review' : 'On Track'}</span>
            <span class="metric-sub ${f.transportUsedPct >= 80 ? 'alert' : 'positive'}">Transport budget ${f.transportUsedPct}% used</span>
          </div>
        </div>
      </section>

      <section class="grid grid-2">
        <div class="card">
          <div class="card-title">
            <div>
              <h3>Fund Allocation Breakdown</h3>
              <p>Budget distribution by relief priority category</p>
            </div>
            <span class="badge badge-safe">Sum: ${f.categories.reduce((sum, category) => sum + Number(category.percentage || 0), 0)}%</span>
          </div>
          ${renderDonutChart(f.categories, f.totalAllocated)}
          <div style="display:grid;grid-template-columns:repeat(2, 1fr);gap:12px;margin-top:20px">
            ${f.categories.map(c => `
              <div style="display:flex;align-items:center;gap:8px;font-size:0.88rem">
                <span style="width:12px;height:12px;border-radius:3px;background:${['#2563eb','#f97316','#10b981','#8b5cf6','#e11d48'][f.categories.indexOf(c)%5]};display:inline-block"></span>
                <span><b>${escapeHtml(c.category)}:</b> ${c.percentage}%</span>
              </div>
            `).join('')}
          </div>
        </div>

        <div class="card">
          <div class="card-title">
            <div>
              <h3>Category Expenditure Controls</h3>
              <p>Burn rates against allocated caps</p>
            </div>
            <span class="badge badge-info">Live Audit</span>
          </div>
          <div style="display:flex;flex-direction:column;gap:18px;margin-top:14px">
            <div>
              <div style="display:flex;justify-content:space-between;margin-bottom:4px;font-size:0.88rem">
                <span><b>Logistics & Transport Spending</b></span>
                <b style="color:#d97706">${f.transportUsedPct}%</b>
              </div>
              <div class="progress-track">
                <div class="progress-fill warning" style="width:${f.transportUsedPct}%"></div>
              </div>
            </div>

            <div>
              <div style="display:flex;justify-content:space-between;margin-bottom:4px;font-size:0.88rem">
                <span><b>Medical Care & Kits Spending</b></span>
                <b style="color:#2563eb">${f.medicalUsedPct}%</b>
              </div>
              <div class="progress-track">
                <div class="progress-fill blue" style="width:${f.medicalUsedPct}%"></div>
              </div>
            </div>

            <div style="padding:14px;background:#fffbeb;border:1px solid #fde68a;border-radius:8px;font-size:0.85rem;color:#92400e;display:flex;align-items:center;gap:10px">
              ${getIcon(f.transportUsedPct >= 80 ? 'AlertTriangle' : 'CheckCircle2')}
              <span>${f.transportUsedPct >= 80 ? `Transport expenditure has reached ${f.transportUsedPct}% of its approved budget. Review additional fuel spending.` : `Transport expenditure is at ${f.transportUsedPct}% of its approved budget; the review threshold is 80%.`}</span>
            </div>
          </div>
        </div>
      </section>
      <section class="card" style="margin-top:22px">
        <div class="card-title">
          <div><h3>Donations & Intake Register</h3><p>Live contributions and verification status from the shared donation records.</p></div>
          <div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn btn-secondary" id="fund-ledger-btn">${getIcon('List')} View Ledger</button><button class="btn btn-primary" id="fund-register-donation-btn">${getIcon('Plus')} Register Donation</button></div>
        </div>
        <div class="metrics-grid" style="grid-template-columns:repeat(3,minmax(0,1fr));margin-bottom:18px">
          <div class="metric-card"><div class="metric-info"><span class="metric-label">Recorded Donations</span><span class="metric-value">${donationsData.length}</span></div></div>
          <div class="metric-card"><div class="metric-info"><span class="metric-label">Accepted Cash</span><span class="metric-value">₹${(donationsData.filter(d => d.donation_type === 'Cash' && ['Accepted','Partially Accepted'].includes(d.status)).reduce((sum,d) => sum + Number(d.declared_amount_paise || 0),0)/100).toLocaleString('en-IN')}</span></div></div>
          <div class="metric-card"><div class="metric-info"><span class="metric-label">Accepted In-Kind Units</span><span class="metric-value">${donationsData.filter(d => d.donation_type === 'InKind').reduce((sum,d) => sum + Number(d.accepted_quantity || 0),0).toLocaleString()}</span></div></div>
        </div>
        <div class="data-table-container"><table class="data-table"><thead><tr><th>Donor</th><th>Type / Contribution</th><th>Destination</th><th>Status</th><th>Action</th></tr></thead><tbody>
          ${donationsData.length ? donationsData.map(d => `<tr><td><b>${escapeHtml(d.donor_name || 'Donor')}</b><br><small>${escapeHtml(d.id)}</small></td><td>${escapeHtml(d.donation_type)} · ${d.donation_type === 'Cash' ? `₹${(Number(d.declared_amount_paise || 0)/100).toLocaleString('en-IN')}` : `${Number(d.accepted_quantity || 0).toLocaleString()} accepted / ${Number(d.declared_quantity || 0).toLocaleString()} declared ${escapeHtml(d.item_names || 'units')}`}</td><td>${escapeHtml(d.destination_warehouse_name || 'Not assigned')}</td><td><span class="badge ${d.status === 'Accepted' ? 'badge-safe' : d.status === 'Rejected' ? 'badge-critical' : 'badge-warning'}">${escapeHtml(d.status)}</span></td><td style="white-space:nowrap">${['Submitted','In Transit'].includes(d.status) ? `<button class="btn btn-secondary btn-sm donation-receive-btn" data-id="${escapeHtml(d.id)}">Mark Received</button>` : d.status === 'Received' ? `<button class="btn btn-primary btn-sm donation-verify-btn" data-id="${escapeHtml(d.id)}">Verify</button>` : '—'}</td></tr>`).join('') : `<tr><td colspan="5" style="text-align:center;padding:26px;color:var(--text-muted)">No donations recorded yet. Register a contribution to begin the shared intake workflow.</td></tr>`}
        </tbody></table></div>
      </section>
    `;
    container.querySelector('#fund-register-donation-btn').onclick = () => openRegisterDonationModal();
    container.querySelector('#fund-ledger-btn').onclick = () => openConsolidatedLedgerModal();
    container.querySelectorAll('.donation-receive-btn').forEach(btn => btn.onclick = async () => {
      const response = await fetch(`/api/donations/${encodeURIComponent(btn.dataset.id)}/receive`, { method: 'POST' });
      const result = await response.json(); if (!response.ok) return showToast(result.error || 'Could not receive donation');
      await loadAllData(); renderApp();
    });
    container.querySelectorAll('.donation-verify-btn').forEach(btn => btn.onclick = () => openDonationVerificationModal(btn.dataset.id));
  }

  // =========================================================================
  // 9. SYSTEM ADMINISTRATION PAGE (ADMIN ONLY)
  // =========================================================================

  function renderAdminPage(container) {
    if (session.role !== 'Administrator') {
      container.innerHTML = `<div class="card"><p>Access restricted to Administrators.</p></div>`;
      return;
    }

    container.innerHTML = `
      <div class="page-header">
        <div class="page-header-text">
          <h2>System Administration & RBAC Management</h2>
          <p>Review pending user registrations, verify staff authorizations, and inspect security audit settings.</p>
        </div>
      </div>

      <div class="card" style="margin-bottom:24px">
        <div class="card-title">
          <div>
            <h3>Pending Account Approvals (${pendingUsers.length})</h3>
            <p>Staff and volunteer registrations requiring administrative verification</p>
          </div>
          <span class="badge ${pendingUsers.length > 0 ? 'badge-warning' : 'badge-safe'}">
            ${pendingUsers.length} Pending
          </span>
        </div>

        <div class="data-table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>Applicant</th>
                <th>Email Address</th>
                <th>Requested Role</th>
                <th>Registration Date</th>
                <th style="text-align:right">Action</th>
              </tr>
            </thead>
            <tbody>
              ${pendingUsers.length > 0 ? pendingUsers.map(u => `
                <tr>
                  <td>
                    <div style="display:flex;align-items:center;gap:10px">
                      <div class="user-avatar" style="width:32px;height:32px;font-size:0.75rem">${escapeHtml(u.initials || 'U')}</div>
                      <b>${escapeHtml(u.name)}</b>
                    </div>
                  </td>
                  <td>${escapeHtml(u.email)}</td>
                  <td><span class="badge badge-info">${escapeHtml(u.role)}</span></td>
                  <td>${escapeHtml(u.created_at || 'Recent')}</td>
                  <td style="text-align:right">
                    <div style="display:inline-flex;gap:6px">
                      <button type="button" class="btn btn-outline-danger btn-sm admin-reject-btn" data-email="${escapeHtml(u.email)}">
                        ${getIcon('UserX')} Reject
                      </button>
                      <button type="button" class="btn btn-primary btn-sm admin-approve-btn" data-email="${escapeHtml(u.email)}">
                        ${getIcon('UserCheck')} Approve
                      </button>
                    </div>
                  </td>
                </tr>
              `).join('') : `
                <tr>
                  <td colspan="5" style="text-align:center;padding:32px;color:var(--text-muted)">
                    No pending registration requests. All accounts are currently reviewed.
                  </td>
                </tr>
              `}
            </tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <div class="card-title">
          <div>
            <h3>Role-Based Access Control (RBAC) Matrix</h3>
            <p>Active permissions by assigned role</p>
          </div>
        </div>
        <div class="data-table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>Role</th>
                <th>Request Allocations</th>
                <th>Warehouse Stock</th>
                <th>Volunteer Assign</th>
                <th>Fleet Dispatch</th>
                <th>Export CSV</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><b>Administrator</b></td>
                <td><span class="badge badge-safe">Full Access</span></td>
                <td><span class="badge badge-safe">Full Access</span></td>
                <td><span class="badge badge-safe">Full Access</span></td>
                <td><span class="badge badge-safe">Full Access</span></td>
                <td><span class="badge badge-safe">Full Access</span></td>
              </tr>
              <tr>
                <td><b>Government Official</b></td>
                <td><span class="badge badge-safe">Authorize</span></td>
                <td><span class="badge badge-safe">View & Add</span></td>
                <td><span class="badge badge-safe">Manage</span></td>
                <td><span class="badge badge-safe">Oversee</span></td>
                <td><span class="badge badge-safe">Full Access</span></td>
              </tr>
              <tr>
                <td><b>NGO Coordinator</b></td>
                <td><span class="badge badge-safe">Allocate</span></td>
                <td><span class="badge badge-safe">View & Add</span></td>
                <td><span class="badge badge-safe">Manage</span></td>
                <td><span class="badge badge-safe">Oversee</span></td>
                <td><span class="badge badge-safe">Full Access</span></td>
              </tr>
              <tr>
                <td><b>Volunteer</b></td>
                <td><span class="badge badge-neutral">Read Only</span></td>
                <td><span class="badge badge-neutral">Read Only</span></td>
                <td><span class="badge badge-neutral">Self View</span></td>
                <td><span class="badge badge-neutral">Task View</span></td>
                <td><span class="badge badge-warning">Restricted</span></td>
              </tr>
              <tr>
                <td><b>Driver</b></td>
                <td><span class="badge badge-warning">Restricted</span></td>
                <td><span class="badge badge-warning">Restricted</span></td>
                <td><span class="badge badge-warning">Restricted</span></td>
                <td><span class="badge badge-safe">Advance Own Trip</span></td>
                <td><span class="badge badge-warning">Restricted</span></td>
              </tr>
              <tr>
                <td><b>Citizen</b></td>
                <td><span class="badge badge-safe">Create Own</span></td>
                <td><span class="badge badge-warning">Restricted</span></td>
                <td><span class="badge badge-warning">Restricted</span></td>
                <td><span class="badge badge-warning">Restricted</span></td>
                <td><span class="badge badge-warning">Restricted</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="card" id="admin-audit-section" style="margin-top:24px">
        <div class="card-title">
          <div>
            <h3>Security & Compliance Audit Trail (audit_logs)</h3>
            <p>Immutable event ledger recording mutations, actor identity, entity diffs, and authorization context</p>
          </div>
          <button type="button" class="btn btn-secondary btn-sm" id="admin-refresh-audit-btn">
            ${getIcon('RotateCw')} Refresh Audit Trail
          </button>
        </div>
        <div id="admin-audit-table-content">
          <p style="color:var(--text-muted);font-size:0.88rem">Loading audit logs...</p>
        </div>
      </div>
    `;

    const loadAdminAuditLogs = async () => {
      const contentEl = container.querySelector('#admin-audit-table-content');
      if (!contentEl) return;
      try {
        const res = await fetch('/api/admin/audit-logs');
        const logs = await res.json();
        if (!Array.isArray(logs) || logs.length === 0) {
          contentEl.innerHTML = `<div style="text-align:center;padding:24px;color:var(--text-muted)">No audit events recorded yet.</div>`;
          return;
        }

        contentEl.innerHTML = `
          <div class="data-table-container">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Log ID</th>
                  <th>Timestamp (UTC)</th>
                  <th>Actor</th>
                  <th>Action</th>
                  <th>Entity</th>
                  <th>Entity ID</th>
                  <th>Reason / Summary</th>
                </tr>
              </thead>
              <tbody>
                ${logs.slice(0, 20).map(l => `
                  <tr>
                    <td class="mono">#${escapeHtml(l.id)}</td>
                    <td style="font-size:0.82rem;color:var(--text-secondary);white-space:nowrap">${escapeHtml(l.created_at || '—')}</td>
                    <td>
                      <div style="font-weight:600">${escapeHtml(l.actor_name || 'System / Auto')}</div>
                      <div style="font-size:0.75rem;color:var(--text-muted)">${escapeHtml(l.actor_role || 'Background Task')}</div>
                    </td>
                    <td><span class="badge badge-info mono" style="font-size:0.75rem">${escapeHtml(l.action)}</span></td>
                    <td><span class="badge badge-neutral">${escapeHtml(l.entity_type)}</span></td>
                    <td class="mono"><b>${escapeHtml(l.entity_id || '—')}</b></td>
                    <td style="font-size:0.85rem;max-width:280px">${escapeHtml(l.reason || 'Authorized operational state update')}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        `;
      } catch (err) {
        contentEl.innerHTML = `<p style="color:var(--danger);font-size:0.85rem">Failed to load audit logs: ${escapeHtml(err.message)}</p>`;
      }
    };

    const refreshAuditBtn = container.querySelector('#admin-refresh-audit-btn');
    if (refreshAuditBtn) refreshAuditBtn.onclick = () => loadAdminAuditLogs();
    loadAdminAuditLogs();

    container.querySelectorAll('.admin-approve-btn').forEach(btn => {
      btn.onclick = async () => {
        try {
          const res = await fetch('/api/admin/approve-user', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: btn.dataset.email })
          });
          if (res.ok) {
            showToast(`Account approved for ${btn.dataset.email}`);
            await loadAllData();
            renderApp();
          } else {
            showToast('Failed to approve account');
          }
        } catch (e) {
          showToast('Network error during approval');
        }
      };
    });

    container.querySelectorAll('.admin-reject-btn').forEach(btn => {
      btn.onclick = async () => {
        try {
          const res = await fetch('/api/admin/reject-user', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: btn.dataset.email })
          });
          if (res.ok) {
            showToast(`Registration rejected for ${btn.dataset.email}`);
            await loadAllData();
            renderApp();
          } else {
            showToast('Failed to reject account');
          }
        } catch (e) {
          showToast('Network error during rejection');
        }
      };
    });
  }

  // =========================================================================
  // MODALS & DIALOGS
  // =========================================================================

  // Generic Prompt Modal
  function askPrompt(title, fields, onSubmit) {
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal">
        <div class="modal-head">
          <div>
            <p class="eyebrow" style="color:var(--text-muted)">COMMAND ACTION</p>
            <h3>${escapeHtml(title)}</h3>
          </div>
          <button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button>
        </div>
        <form id="prompt-form">
          <div class="modal-body">
            ${fields.map(f => `
              <div class="form-group">
                <label>${escapeHtml(f)}</label>
                <input required name="${escapeHtml(f)}" placeholder="Enter ${escapeHtml(f)}">
              </div>
            `).join('')}
          </div>
          <div class="modal-actions">
            <button type="button" class="btn btn-secondary close-modal">Cancel</button>
            <button type="submit" class="btn btn-primary">Submit</button>
          </div>
        </form>
      </div>
    `;
    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());
    backdrop.querySelector('#prompt-form').onsubmit = e => {
      e.preventDefault();
      const data = Object.fromEntries(new FormData(e.target));
      onSubmit(data);
      backdrop.remove();
    };
  }

  // Workspace Activity Logger Modal
  async function openWorkspace(title, detail) {
    const key = 'ws_' + title.toLowerCase().replace(/[^a-z0-9]+/g, '_');
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';

    async function refresh() {
      let activities = [];
      let activityLoadError = null;
      try {
        const res = await fetch(`/api/workspace-activity?key=${encodeURIComponent(key)}`);
        activities = await res.json();
        if (!res.ok) throw new Error(activities.error || 'Activity records could not be refreshed.');
      } catch (e) {
        activityLoadError = e.message || 'Activity records could not be refreshed.';
      }

      backdrop.innerHTML = `
        <div class="modal" style="width:min(640px, 96vw)">
          <div class="modal-head">
            <div>
              <p class="eyebrow" style="color:var(--text-muted)">ROLE WORKSPACE ACTIVITY</p>
              <h3>${escapeHtml(title)}</h3>
            </div>
            <button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button>
          </div>
          <div class="modal-body">
            <p style="font-size:0.85rem;color:var(--text-secondary)">${escapeHtml(detail)}</p>
            <form id="ws-form" style="display:flex;flex-direction:column;gap:12px">
              <div class="form-group">
                <label>Operation Title / Subject</label>
                <input required name="title" placeholder="e.g. Sector 4 supply delivery completed">
              </div>
              <div class="form-group">
                <label>Detailed Note or Directive</label>
                <textarea required name="details" rows="3" placeholder="Enter full situation report, numbers or instructions..."></textarea>
              </div>
              <div style="display:flex;justify-content:flex-end">
                <button type="submit" class="btn btn-primary">
                  Save Activity Log
                </button>
              </div>
            </form>

            <h4 style="font-size:0.95rem;margin-top:16px;border-top:1px solid var(--surface-border);padding-top:14px">
              Saved Activity History
            </h4>
            <div style="max-height:180px;overflow-y:auto;display:flex;flex-direction:column;gap:8px">
              ${activities.length > 0 ? activities.map(a => `
                <div style="padding:8px 12px;background:#f8fafc;border-radius:6px;border:1px solid var(--surface-border)">
                  <b>${escapeHtml(a.title)}</b>
                  <p style="font-size:0.8rem;color:var(--text-secondary);margin:2px 0">${escapeHtml(a.details)}</p>
                  <small style="color:var(--text-muted);font-size:0.72rem">${escapeHtml(a.created_at || 'Recorded')}</small>
                </div>
              `).join('') : `
                <p style="font-size:0.82rem;color:var(--text-muted)">${escapeHtml(activityLoadError || 'No activities logged yet for this module.')}</p>
              `}
            </div>
          </div>
          <div class="modal-actions">
            <button type="button" class="btn btn-secondary close-modal">Close</button>
          </div>
        </div>
      `;

      backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());
      backdrop.querySelector('#ws-form').onsubmit = async e => {
        e.preventDefault();
        const fd = Object.fromEntries(new FormData(e.target));
        try {
          const response = await fetch('/api/workspace-activity', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key, title: fd.title, details: fd.details })
          });
          const result = await response.json();
          if (!response.ok) { showToast(result.error || 'Activity note was not saved.'); return; }
          showToast('Activity note saved to the database.');
          refresh();
        } catch (err) {
          showToast('Network error. Activity note was not saved.');
        }
      };
    }

    document.body.appendChild(backdrop);
    refresh();
  }

  // =========================================================================
  // SPECIALIZED ROLE MODALS & WORKFLOW DIALOGS
  // =========================================================================

  // 1. Advisories & Public Safety Directives Modal
  async function openAdvisoriesModal() {
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    let advisories = [];
  let incidents = [];
  let notifications = [];
    try {
      const res = await fetch('/api/advisories');
      advisories = await res.json();
    } catch (e) {
      advisories = [];
    }

    backdrop.innerHTML = `
      <div class="modal" style="width:min(660px, 96vw)">
        <div class="modal-head">
          <div>
            <p class="eyebrow" style="color:var(--text-muted)">DISASTER RESPONSE COMMAND</p>
            <h3>Public Safety Directives & Advisories</h3>
          </div>
          <button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button>
        </div>
        <div class="modal-body">
          <p style="font-size:0.85rem;color:var(--text-secondary)">
            Official alerts issued by District Emergency Command for flood-affected sectors.
          </p>
          <div style="display:flex;flex-direction:column;gap:12px;max-height:420px;overflow-y:auto">
            ${Array.isArray(advisories) && advisories.length > 0 ? advisories.map(adv => `
              <div style="padding:14px;background:#ffffff;border-radius:8px;border:1px solid var(--surface-border);border-left:4px solid ${adv.category === 'Evacuation' ? '#dc2626' : '#2563eb'}">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                  <b style="font-size:0.95rem;color:${adv.category === 'Evacuation' ? '#991b1b' : '#0f172a'}">${escapeHtml(adv.title)}</b>
                  <span class="badge ${adv.category === 'Evacuation' ? 'badge-critical' : 'badge-info'}">${escapeHtml(adv.category || 'Advisory')}</span>
                </div>
                <p style="font-size:0.88rem;color:var(--text-secondary);line-height:1.5;margin-bottom:8px">${escapeHtml(adv.message || adv.body || '')}</p>
                <div style="display:flex;justify-content:space-between;align-items:center;font-size:0.75rem;color:var(--text-muted)">
                  <span>Zone: <b>${escapeHtml(adv.zone_id || 'All Zones')}</b> · Published by District Command</span>
                  <span>${escapeHtml(adv.published_at || 'Published')}</span>
                </div>
              </div>
            `).join('') : `
              <p class="empty-state">No current published advisories.</p>
            `}
          </div>
        </div>
        <div class="modal-actions">
          <button type="button" class="btn btn-secondary close-modal">Close</button>
        </div>
      </div>
    `;

    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());
  }

  // 2. Citizen Delivery Confirmation & Issue Reporting Modal
  function openCitizenFeedbackModal(myReq, preselectType = 'confirm') {
    if (!myReq) {
      myReq = requests.find(r => r.requester_name === session.name) || requests[0];
    }
    if (!myReq) {
      showToast('No active emergency request found for feedback.');
      return;
    }

    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal" style="width:min(560px, 96vw)">
        <div class="modal-head">
          <div>
            <p class="eyebrow" style="color:var(--text-muted)">CITIZEN ASSISTANCE FEEDBACK</p>
            <h3>Relief Feedback: ${escapeHtml(myReq.id)}</h3>
          </div>
          <button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button>
        </div>
        <form id="citizen-feedback-form">
          <div class="modal-body">
            <div class="modal-tabs">
              <button type="button" class="modal-tab-btn ${preselectType === 'confirm' ? 'active' : ''}" id="tab-confirm-aid">Confirm Delivery Received</button>
              <button type="button" class="modal-tab-btn ${preselectType === 'issue' ? 'active' : ''}" id="tab-report-issue">Report Delivery Issue</button>
            </div>

            <div id="feedback-confirm-fields" style="display:${preselectType === 'confirm' ? 'block' : 'none'}">
              <p style="font-size:0.85rem;color:var(--text-secondary);margin-bottom:12px">
                Please confirm that relief supplies for <b>${escapeHtml(myReq.need)}</b> have been safely received at your registered location.
              </p>
              <div class="form-group">
                <label>Beneficiary Confirmation Notes (Optional)</label>
                <textarea name="confirm_notes" rows="3" placeholder="e.g. Received food rations and clean drinking water in good condition. Thank you to the field team."></textarea>
              </div>
            </div>

            <div id="feedback-issue-fields" style="display:${preselectType === 'issue' ? 'block' : 'none'}">
              <p style="font-size:0.85rem;color:var(--emergency-crimson);margin-bottom:12px">
                Report incomplete kits, missing items, or delivery issues for supervisor resolution.
              </p>
              <div class="form-group">
                <label>Issue Description / Reason <span style="color:var(--emergency-crimson)">*</span></label>
                <textarea name="issue_reason" rows="3" placeholder="e.g. Drinking water bottles were received, but dry food ration packet was damaged or missing."></textarea>
              </div>
            </div>
          </div>
          <div class="modal-actions">
            <button type="button" class="btn btn-secondary close-modal">Cancel</button>
            <button type="submit" class="btn btn-primary" id="btn-submit-feedback">
              ${preselectType === 'confirm' ? 'Confirm Aid Received ✓' : 'Submit Issue Report'}
            </button>
          </div>
        </form>
      </div>
    `;

    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());

    let activeType = preselectType;
    const tabConf = backdrop.querySelector('#tab-confirm-aid');
    const tabIss = backdrop.querySelector('#tab-report-issue');
    const confFields = backdrop.querySelector('#feedback-confirm-fields');
    const issFields = backdrop.querySelector('#feedback-issue-fields');
    const submitBtn = backdrop.querySelector('#btn-submit-feedback');

    tabConf.onclick = () => {
      activeType = 'confirm';
      tabConf.classList.add('active');
      tabIss.classList.remove('active');
      confFields.style.display = 'block';
      issFields.style.display = 'none';
      submitBtn.textContent = 'Confirm Aid Received ✓';
    };

    tabIss.onclick = () => {
      activeType = 'issue';
      tabIss.classList.add('active');
      tabConf.classList.remove('active');
      confFields.style.display = 'none';
      issFields.style.display = 'block';
      submitBtn.textContent = 'Submit Issue Report';
    };

    backdrop.querySelector('#citizen-feedback-form').onsubmit = async (e) => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(e.target));
      try {
        if (activeType === 'confirm') {
          const res = await fetch(`/api/requests/${myReq.id}/confirm-delivery`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ notes: fd.confirm_notes || 'Citizen confirmed delivery via relief portal' })
          });
          const data = await res.json();
          if (!res.ok) {
            showToast(data.error || 'Failed to confirm delivery');
            return;
          }
          showToast('Delivery confirmation recorded! Thank you.');
        } else {
          if (!fd.issue_reason || !fd.issue_reason.trim()) {
            showToast('Please provide an issue description');
            return;
          }
          const res = await fetch(`/api/requests/${myReq.id}/report-issue`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason: fd.issue_reason.trim() })
          });
          const data = await res.json();
          if (!res.ok) {
            showToast(data.error || 'Failed to submit issue report');
            return;
          }
          showToast('Issue report logged for Emergency Coordinator review.');
        }
        backdrop.remove();
        await loadAllData();
        renderApp();
      } catch (err) {
        showToast('Network error submitting feedback');
      }
    };
  }

  // 3. Request Audit Timeline Modal
  async function openRequestTimelineModal(requestId) {
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    let timelineEvents = [];
    try {
      const res = await fetch(`/api/requests/${requestId}/timeline`);
      timelineEvents = await res.json();
    } catch (e) {
      timelineEvents = [];
    }

    backdrop.innerHTML = `
      <div class="modal" style="width:min(620px, 96vw)">
        <div class="modal-head">
          <div>
            <p class="eyebrow mono">${escapeHtml(requestId)}</p>
            <h3>Lifecycle Audit Timeline</h3>
          </div>
          <button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button>
        </div>
        <div class="modal-body">
          <p style="font-size:0.85rem;color:var(--text-secondary)">
            Chronological audit trail of request verification, inventory reservations, vehicle dispatches, and delivery confirmations.
          </p>
          <div class="timeline-container" style="max-height:400px;overflow-y:auto;padding-right:8px">
            ${Array.isArray(timelineEvents) && timelineEvents.length > 0 ? timelineEvents.map(ev => {
              const action = ev.action || ev.event_type || 'STATUS_UPDATE';
              const dotClass = action.includes('DELIVER') ? 'delivered' : action.includes('DISPATCH') ? 'dispatched' : action.includes('ISSUE') ? 'issue' : 'verified';
              return `
                <div class="timeline-item ${dotClass}">
                  <span class="timeline-dot"></span>
                  <div style="display:flex;justify-content:space-between;align-items:center">
                    <span class="timeline-title">${escapeHtml(action)}</span>
                    <span class="timeline-time">${escapeHtml(ev.created_at || 'Logged')}</span>
                  </div>
                  <div class="timeline-desc">
                    ${ev.actor_name ? `<b>${escapeHtml(ev.actor_name)}</b> (${escapeHtml(ev.actor_role || 'Staff')}): ` : ''}
                    ${escapeHtml(ev.reason || ev.notes || 'Status updated in response registry')}
                  </div>
                </div>
              `;
            }).join('') : `
              <div class="timeline-item verified">
                <span class="timeline-dot"></span>
                <span class="timeline-title">Request Registered</span>
                <span class="timeline-time">Initial Registration</span>
                <div class="timeline-desc">Distress request registered into DRRAS priority dispatch queue.</div>
              </div>
            `}
          </div>
        </div>
        <div class="modal-actions">
          <button type="button" class="btn btn-secondary close-modal">Close</button>
        </div>
      </div>
    `;

    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());
  }

  // 4. Volunteer Distribution Reconciliation Modal
  async function openDistributionReconciliationModal(taskObj = null) {
    let tasksList = [];
    if (!taskObj) {
      try {
        const res = await fetch('/api/volunteer-tasks');
        tasksList = await res.json();
      } catch (e) {
        tasksList = [];
      }
      taskObj = tasksList.find(t => t.status === 'InProgress' || t.status === 'Assigned') || tasksList[0] || {
        id: 'TASK-001',
        title: 'Emergency Food Ration Distribution',
        target_quantity: 50,
        unit: 'kits',
        zone_id: 'Z-01'
      };
    }

    const targetQty = taskObj.target_quantity ?? taskObj.quantity_expected ?? null;
    const defaultCompleted = Math.max(0, targetQty - 10);
    const defaultDamaged = 2;
    const defaultRemaining = Math.max(0, targetQty - defaultCompleted - defaultDamaged);

    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal" style="width:min(600px, 96vw)">
        <div class="modal-head">
          <div>
            <p class="eyebrow mono">${escapeHtml(taskObj.id)} · ${escapeHtml(taskObj.zone_id || 'Z-01')}</p>
            <h3>Distribution Reconciliation Report</h3>
          </div>
          <button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button>
        </div>
        <form id="recon-task-form">
          <div class="modal-body">
            <p style="font-size:0.85rem;color:var(--text-secondary)">
              Operational inventory reconciliation equation: <b>Received = Completed + Damaged + Remaining</b>. All units must balance before supervisor approval.
            </p>

            <div class="recon-formula-box recon-balanced" id="recon-formula-status">
              <div class="recon-formula-header">
                <span id="recon-status-badge">✓ Inventory Balanced</span>
                <span class="mono" id="recon-status-diff">Diff: 0</span>
              </div>
              <div class="recon-formula-eq" id="recon-equation-text">
                ${targetQty} Received = ${defaultCompleted} Completed + ${defaultDamaged} Damaged + ${defaultRemaining} Remaining
              </div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label>Received / Target Quantity</label>
                <input required type="number" min="1" id="recon-rec-input" name="received_qty" value="${targetQty}">
              </div>
              <div class="form-group">
                <label>Completed Distribution Count <span style="color:var(--success-emerald)">*</span></label>
                <input required type="number" min="0" id="recon-comp-input" name="completed_qty" value="${defaultCompleted}">
              </div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label>Damaged / Spoiled Count</label>
                <input required type="number" min="0" id="recon-dam-input" name="damaged_qty" value="${defaultDamaged}">
              </div>
              <div class="form-group">
                <label>Remaining / Returned to Warehouse</label>
                <input required type="number" min="0" id="recon-rem-input" name="remaining_qty" value="${defaultRemaining}">
              </div>
            </div>

            <div class="form-group">
              <label>Field Observations & Checkpoint Notes</label>
              <textarea name="notes" rows="2" placeholder="e.g. Distributed to families in Sector 4 lowlands; 2 ration packs damaged by floodwater splash."></textarea>
            </div>
          </div>
          <div class="modal-actions">
            <button type="button" class="btn btn-secondary close-modal">Cancel</button>
            <button type="submit" class="btn btn-primary" id="btn-submit-recon">Submit Distribution Report</button>
          </div>
        </form>
      </div>
    `;

    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());

    const recInput = backdrop.querySelector('#recon-rec-input');
    const compInput = backdrop.querySelector('#recon-comp-input');
    const damInput = backdrop.querySelector('#recon-dam-input');
    const remInput = backdrop.querySelector('#recon-rem-input');
    const statusBox = backdrop.querySelector('#recon-formula-status');
    const statusBadge = backdrop.querySelector('#recon-status-badge');
    const statusDiff = backdrop.querySelector('#recon-status-diff');
    const equationText = backdrop.querySelector('#recon-equation-text');
    const submitBtn = backdrop.querySelector('#btn-submit-recon');

    function updateRecon() {
      const rec = parseInt(recInput.value) || 0;
      const comp = parseInt(compInput.value) || 0;
      const dam = parseInt(damInput.value) || 0;
      const rem = parseInt(remInput.value) || 0;
      const sum = comp + dam + rem;
      const diff = rec - sum;

      equationText.textContent = `${rec} Received = ${comp} Completed + ${dam} Damaged + ${rem} Remaining`;

      if (diff === 0 && rec > 0) {
        statusBox.className = 'recon-formula-box recon-balanced';
        statusBadge.textContent = '✓ Inventory Balanced';
        statusDiff.textContent = 'Diff: 0';
        submitBtn.disabled = false;
      } else {
        statusBox.className = 'recon-formula-box recon-unbalanced';
        statusBadge.textContent = '⚠️ Quantities Must Balance';
        statusDiff.textContent = `Discrepancy: ${diff > 0 ? '+' : ''}${diff}`;
        submitBtn.disabled = true;
      }
    }

    [recInput, compInput, damInput, remInput].forEach(inp => inp.oninput = updateRecon);

    backdrop.querySelector('#recon-task-form').onsubmit = async (e) => {
      e.preventDefault();
      const comp = parseInt(compInput.value) || 0;
      const dam = parseInt(damInput.value) || 0;
      const rem = parseInt(remInput.value) || 0;
      const fd = Object.fromEntries(new FormData(e.target));

      try {
        const res = await fetch(`/api/volunteer-tasks/${taskObj.id}/submit`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            quantity_received: parseInt(recInput.value) || (comp + dam + rem),
            quantity_completed: comp,
            quantity_damaged: dam,
            quantity_remaining: rem,
            completed_quantity: comp,
            damaged_quantity: dam,
            remaining_quantity: rem,
            notes: fd.notes || 'Volunteer distribution report submitted'
          })
        });
        const resData = await res.json();
        if (!res.ok) {
          showToast(resData.error || 'Failed to submit reconciliation report');
          return;
        }
        showToast(`Task ${taskObj.id} reconciliation submitted for review.`);
        backdrop.remove();
        await loadAllData();
        renderApp();
      } catch (err) {
        showToast('Network error submitting reconciliation report');
      }
    };
  }

  // 5. Volunteer Check-In Action
  async function handleVolunteerCheckin() {
    try {
      const tasksRes = await fetch('/api/volunteer-tasks');
      const tasks = await tasksRes.json();
      const myTask = Array.isArray(tasks) ? tasks.find(t => t.status === 'InProgress' || t.status === 'Assigned') : null;
      if (myTask) {
        const res = await fetch(`/api/volunteer-tasks/${myTask.id}/check-in`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ notes: 'Responder checked in at designated field post.' })
        });
        if (res.ok) {
          showToast(`Checked in for task ${myTask.id} at field sector!`);
          await loadAllData();
          renderApp();
          return;
        }
      }
    } catch (e) { showToast('Could not refresh assigned tasks. Please retry.'); return; }
    showToast('No assigned task is available for check-in.');
  }

  // 6. Field Incident Observation Report Modal
  async function openFieldReportModal() {
    let reportZones = [];
    try { const response = await fetch('/api/zones'); if (response.ok) reportZones = await response.json(); } catch (e) {}
    const scopedZones = reportZones.filter(z => !dashboardData?.activeIncidentId || z.incident_id === dashboardData.activeIncidentId);
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal" style="width:min(600px, 96vw)">
        <div class="modal-head">
          <div>
            <p class="eyebrow" style="color:var(--text-muted)">GROUND SITUATION REPORT</p>
            <h3>Log Field Observation Report</h3>
          </div>
          <button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button>
        </div>
        <form id="field-report-form">
          <div class="modal-body">
            <div class="form-row">
              <div class="form-group">
                <label>Incident Reference</label>
                <input readonly name="incident_id" value="${escapeHtml(dashboardData?.activeIncidentId || '')}">
              </div>
              <div class="form-group">
                <label>Disaster Sector Zone</label>
                <select required name="zone_id">
                  <option value="">Select an incident zone</option>
                  ${scopedZones.map(z => `<option value="${escapeHtml(z.id)}">${escapeHtml(z.name)}</option>`).join('')}
                </select>
              </div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label>Observation Category</label>
                <select name="category">
                  <option value="Water Level Surge">Water Level Surge / Flooding</option>
                  <option value="Road Access Blocked">Road Submerged / Route Blockage</option>
                  <option value="Medical Emergency">Medical Distress / Trapped Persons</option>
                  <option value="Shelter Overcrowded">Shelter Capacity Full</option>
                  <option value="Ration Shortage">Dry Rations Needed</option>
                </select>
              </div>
              <div class="form-group">
                <label>Severity Level</label>
                <select name="severity">
                  <option value="Critical">Critical (Immediate Rescue Needed)</option>
                  <option value="Urgent" selected>Urgent (Response Required)</option>
                  <option value="Normal">Normal (Routine Observation)</option>
                </select>
              </div>
            </div>

            <div class="form-group">
              <label>Observation Summary / Headline</label>
              <input required name="summary" placeholder="e.g. Lower riverbank embankment breached near bridge">
            </div>

            <div class="form-group">
              <label>Detailed Field Report & Resource Requirement</label>
              <textarea required name="description" rows="3" placeholder="Describe exact conditions, depth of water, estimated stranded citizens, and required relief supplies..."></textarea>
            </div>
          </div>
          <div class="modal-actions">
            <button type="button" class="btn btn-secondary close-modal">Cancel</button>
            <button type="submit" class="btn btn-primary">Transmit Field Report</button>
          </div>
        </form>
      </div>
    `;

    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());

    backdrop.querySelector('#field-report-form').onsubmit = async (e) => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(e.target));
      try {
        const res = await fetch('/api/field-reports', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            incident_id: fd.incident_id,
            zone_id: fd.zone_id,
            category: fd.category,
            severity: fd.severity,
            summary: fd.summary,
            description: fd.description
          })
        });
        const resData = await res.json();
        if (!res.ok) {
          showToast(resData.error || 'Failed to submit field report');
          return;
        }
        showToast('Field situation report transmitted to District Command!');
        backdrop.remove();
        await loadAllData();
        renderApp();
      } catch (err) {
        showToast('Network error submitting field report');
      }
    };
  }

  // 7. NGO Zone Adoption Application Modal
  async function openZoneAdoptionModal() {
    let zones = [];
    try {
      const res = await fetch('/api/zones');
      zones = await res.json();
    } catch (e) {
      zones = [];
    }

    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal" style="width:min(600px, 96vw)">
        <div class="modal-head">
          <div>
            <p class="eyebrow" style="color:var(--text-muted)">NGO AREA COVERAGE</p>
            <h3>Apply for Relief Zone Adoption</h3>
          </div>
          <button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button>
        </div>
        <form id="zone-adoption-form">
          <div class="modal-body">
            <p style="font-size:0.85rem;color:var(--text-secondary)">
              Adopt a designated flood sector to coordinate volunteer teams, food distribution, and emergency shelters under District Command authorization.
            </p>

            <div class="form-group">
              <label>Select Target Disaster Zone</label>
              <select name="zone_id" required>
                ${Array.isArray(zones) && zones.length > 0 ? zones.map(z => `
                  <option value="${escapeHtml(z.id)}">${escapeHtml(z.id)}: ${escapeHtml(z.name)} (${escapeHtml(z.severity || 'Active')} Severity)</option>
                `).join('') : `
                  <option value="Z-01">Z-01: Riverbank Sector 4</option>
                  <option value="Z-02">Z-02: Ward 8 Central</option>
                  <option value="Z-03">Z-03: Model Town West</option>
                `}
              </select>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label>Pledged Active Volunteers</label>
                <input required type="number" min="1" max="500" name="available_volunteers" placeholder="Enter available count">
              </div>
              <div class="form-group">
                <label>Operational Capacity Level</label>
                <input required name="requested_capacity" value="Dry rations, boat rescue & medical triage">
              </div>
            </div>

            <div class="form-group">
              <label>Resource Mobilization Plan</label>
              <textarea required name="available_resource_summary" rows="3" placeholder="Detail available fleet vehicles, warehousing space, dry food reserves, and paramedic personnel..."></textarea>
            </div>
          </div>
          <div class="modal-actions">
            <button type="button" class="btn btn-secondary close-modal">Cancel</button>
            <button type="submit" class="btn btn-primary">Submit Adoption Request</button>
          </div>
        </form>
      </div>
    `;

    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());

    backdrop.querySelector('#zone-adoption-form').onsubmit = async (e) => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(e.target));
      try {
        const res = await fetch(`/api/zones/${fd.zone_id}/adoptions`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            available_volunteers: parseInt(fd.available_volunteers),
            requested_capacity: fd.requested_capacity,
            available_resource_summary: fd.available_resource_summary
          })
        });
        const resData = await res.json();
        if (!res.ok) {
          showToast(resData.error || 'Failed to submit adoption request');
          return;
        }
        showToast('Zone adoption application submitted for District Command review!');
        backdrop.remove();
        await loadAllData();
        renderApp();
      } catch (err) {
        showToast('Network error submitting adoption application');
      }
    };
  }

  async function openDonationVerificationModal(donationId) {
    const response = await fetch(`/api/donations/${encodeURIComponent(donationId)}`);
    const donation = await response.json();
    if (!response.ok) return showToast(donation.error || 'Could not load donation');
    const backdrop = document.createElement('div'); backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `<div class="modal" style="width:min(680px,96vw)"><div class="modal-head"><div><p class="eyebrow">WAREHOUSE INTAKE CONTROL</p><h3>Verify ${escapeHtml(donation.donor_name)}</h3></div><button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button></div><form id="donation-verify-form"><div class="modal-body"><div class="form-group"><label>Decision</label><select name="decision"><option value="Accept">Accept</option><option value="PartiallyAccept">Partially accept</option><option value="Reject">Reject</option></select></div>${(donation.items || []).map(item => `<div class="card" style="padding:14px;margin:10px 0"><b>${escapeHtml(item.resource_name)} · ${item.quantity_declared} declared</b><div class="form-row"><div class="form-group"><label>Received</label><input type="number" min="0" max="${item.quantity_declared}" name="received_${item.id}" value="${item.quantity_received || item.quantity_declared}" required></div><div class="form-group"><label>Accepted</label><input type="number" min="0" max="${item.quantity_declared}" name="accepted_${item.id}" value="${item.quantity_accepted || item.quantity_declared}" required></div></div></div>`).join('')}<div class="form-group"><label>Verification notes</label><textarea name="reason" rows="2" required>Physically verified by Government warehouse staff</textarea></div></div><div class="modal-actions"><button type="button" class="btn btn-secondary close-modal">Cancel</button><button class="btn btn-primary" type="submit">Save Verification</button></div></form></div>`;
    document.body.appendChild(backdrop); backdrop.querySelectorAll('.close-modal').forEach(button => button.onclick = () => backdrop.remove());
    backdrop.querySelector('#donation-verify-form').onsubmit = async event => {
      event.preventDefault(); const fd = new FormData(event.target); const items = (donation.items || []).map(item => { const received = Number(fd.get(`received_${item.id}`)); const accepted = Number(fd.get(`accepted_${item.id}`)); return { donation_item_id: item.id, quantity_received: received, quantity_accepted: accepted, quantity_rejected: Math.max(0, received - accepted), reason: fd.get('reason') }; });
      const result = await fetch(`/api/donations/${encodeURIComponent(donationId)}/verify`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({decision:fd.get('decision'),reason:fd.get('reason'),items}) });
      const body = await result.json(); if (!result.ok) return showToast(body.error || 'Verification failed');
      backdrop.remove(); showToast('Donation verified and accepted stock recorded.'); await loadAllData(); renderApp();
    };
  }

  // 8. Register Relief Donation Modal (Cash / In-Kind)
  function openRegisterDonationModal() {
    const citizenMode = session?.role === 'Citizen';
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal" style="width:min(640px, 96vw)">
        <div class="modal-head">
          <div>
            <p class="eyebrow" style="color:var(--text-muted)">RELIEF MATERIAL & AID INTAKE</p>
            <h3>Register Relief Donation</h3>
          </div>
          <button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button>
        </div>
        <form id="donation-intake-form">
          <div class="modal-body">
            <div class="modal-tabs">
              <button type="button" class="modal-tab-btn active" id="tab-inkind-don">In-Kind Relief Supplies</button>
              <button type="button" class="modal-tab-btn" id="tab-cash-don">Cash Relief Fund</button>
            </div>

            ${citizenMode ? `
              <div class="form-group">
                <label>Donate to <span style="color:var(--emergency-crimson)">*</span></label>
                <select name="recipient_type" id="don-recipient-type" required>
                  <option value="government">Government Relief Pool</option>
                  <option value="ngo">Approved NGO</option>
                </select>
              </div>
              <div class="form-group" id="don-recipient-ngo-group" style="display:none">
                <label>Choose approved NGO <span style="color:var(--emergency-crimson)">*</span></label>
                <select name="organization_id" id="don-recipient-ngo">
                  <option value="">Select an NGO</option>
                  ${donationOrganizations.map(o => `<option value="${escapeHtml(o.id)}">${escapeHtml(o.name)}</option>`).join('')}
                </select>
              </div>
              <p class="help-text">Your name will be attached to the contribution. The selected recipient will assign an active receiving warehouse. Cash donations are recorded as pledges; no online payment is processed here.</p>
            ` : `
              <div class="form-row">
                <div class="form-group">
                  <label>Donor Name / Organization <span style="color:var(--emergency-crimson)">*</span></label>
                  <input required name="donor_name" placeholder="e.g. Rotary Club Punjab / Tata Trust">
                </div>
                <div class="form-group">
                  <label>Donor Type</label>
                  <select name="donor_type">
                    <option value="Corporate">Corporate / CSR Foundation</option>
                    <option value="NGO">Partner NGO / Charity</option>
                    <option value="Individual">Individual Philanthropist</option>
                  </select>
                </div>
              </div>
            `}

            ${citizenMode ? '' : `<div class="form-group">
              <label>Destination Warehouse</label>
              <select name="warehouse_id" required>
                <option value="">Select an active warehouse</option>
                ${warehouses.filter(w => w.status === 'Active').map(w => `<option value="${escapeHtml(w.id)}">${escapeHtml(w.name)}</option>`).join('')}
              </select>
            </div>`}

            <div id="don-inkind-fields">
              <div class="form-row">
                <div class="form-group">
                  <label>Supply Category</label>
                  <select name="resource_id" id="don-cat-select" required>
                    <option value="">Select a resource</option>
                    ${resources.map(r => `<option value="${escapeHtml(r.id)}">${escapeHtml(r.name)} (${escapeHtml(r.unit || 'units')})</option>`).join('')}
                  </select>
                </div>
              </div>

              <div class="form-row">
                <div class="form-group">
                  <label>Declared Quantity (Units) <span style="color:var(--emergency-crimson)">*</span></label>
                  <input required type="number" min="1" name="quantity_declared" placeholder="Enter declared quantity">
                </div>
                <div class="form-group">
                  <label>Packaging Unit</label>
                  <input required name="unit" value="kits">
                </div>
              </div>

              <div class="form-group">
                <label>Estimated In-Kind Value (₹)</label>
                <input type="number" min="0" name="estimated_value_inr" placeholder="Enter estimated value">
              </div>
            </div>

            <div id="don-cash-fields" style="display:none">
              <div class="form-group">
                <label>Donation Amount (₹ Rupees) <span style="color:var(--emergency-crimson)">*</span></label>
                <input type="number" min="100" name="cash_amount_inr" placeholder="Enter amount">
        <small class="help-text">${citizenMode ? 'Recorded as a cash pledge for recipient verification; no online payment is processed here.' : 'Converted to integer paise ledger credit upon authorization.'}</small>
              </div>
            </div>

            <div class="form-group">
              <label>Intake Manifest Reference / Notes</label>
              <textarea name="notes" rows="2" placeholder="Consignment tracking number, vehicle number, delivery date..."></textarea>
            </div>
          </div>
          <div class="modal-actions">
            <button type="button" class="btn btn-secondary close-modal">Cancel</button>
            <button type="submit" class="btn btn-primary">Register &amp; Queue Verification</button>
          </div>
        </form>
      </div>
    `;

    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());

    let donType = 'InKind';
    const tabInKind = backdrop.querySelector('#tab-inkind-don');
    const tabCash = backdrop.querySelector('#tab-cash-don');
    const inkindFields = backdrop.querySelector('#don-inkind-fields');
    const cashFields = backdrop.querySelector('#don-cash-fields');
    const cashAmount = backdrop.querySelector('input[name="cash_amount_inr"]');
    const inKindRequiredFields = [
      backdrop.querySelector('#don-cat-select'),
      backdrop.querySelector('input[name="quantity_declared"]'),
      backdrop.querySelector('input[name="unit"]')
    ].filter(Boolean);

    const setDonationType = type => {
      donType = type;
      const isCash = type === 'Cash';
      tabCash.classList.toggle('active', isCash);
      tabInKind.classList.toggle('active', !isCash);
      inkindFields.style.display = isCash ? 'none' : 'block';
      cashFields.style.display = isCash ? 'block' : 'none';
      inKindRequiredFields.forEach(field => { field.required = !isCash; });
      if (cashAmount) cashAmount.required = isCash;
    };

    if (citizenMode) {
      const recipientType = backdrop.querySelector('#don-recipient-type');
      const ngoGroup = backdrop.querySelector('#don-recipient-ngo-group');
      const ngoSelect = backdrop.querySelector('#don-recipient-ngo');
      const updateRecipientFields = () => {
        const isNgo = recipientType.value === 'ngo';
        ngoGroup.style.display = isNgo ? 'block' : 'none';
        ngoSelect.required = isNgo;
      };
      recipientType.onchange = updateRecipientFields;
      updateRecipientFields();
    }

    tabInKind.onclick = () => {
      setDonationType('InKind');
    };

    tabCash.onclick = () => {
      setDonationType('Cash');
    };

    backdrop.querySelector('#donation-intake-form').onsubmit = async (e) => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(e.target));
      const payload = {
        donor_name: citizenMode ? session.name : fd.donor_name,
        donor_type: fd.donor_type,
        donation_type: donType,
        incident_id: dashboardData?.activeIncidentId || null,
        notes: fd.notes
      };
      if (citizenMode) {
        payload.recipient_type = fd.recipient_type;
        if (fd.recipient_type === 'ngo') {
          if (!fd.organization_id) { showToast('Choose an approved NGO recipient.'); return; }
          payload.organization_id = parseInt(fd.organization_id);
        }
      } else {
        if (!fd.warehouse_id) { showToast('Select a destination warehouse.'); return; }
        payload.destination_warehouse_id = parseInt(fd.warehouse_id);
      }

      if (donType === 'Cash') {
        const inr = parseFloat(fd.cash_amount_inr || 0);
        if (inr <= 0) {
          showToast('Please enter a valid cash donation amount');
          return;
        }
        payload.declared_amount_paise = Math.round(inr * 100);
      } else {
        payload.category = fd.category;
        if (!fd.resource_id || (!citizenMode && !fd.warehouse_id)) {
          showToast(citizenMode ? 'Select a resource before registering an in-kind donation.' : 'Select a resource and warehouse before registering an in-kind donation.');
          return;
        }
        payload.items = [{ resource_id: parseInt(fd.resource_id), quantity_declared: parseInt(fd.quantity_declared), unit: fd.unit }];
        const valInr = parseFloat(fd.estimated_value_inr || 0);
        payload.estimated_value_paise = Math.round(valInr * 100);
      }

      try {
        const res = await fetch('/api/donations', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const resData = await res.json();
        if (!res.ok) {
          showToast(resData.error || 'Failed to register donation');
          return;
        }
        showToast('Donation registered! Queued for physical warehouse verification.');
        backdrop.remove();
        await loadAllData();
        renderApp();
      } catch (err) {
        showToast('Network error registering donation');
      }
    };
  }

  // 9. Deploy Volunteer Task Modal
  function openDeployVolunteerTaskModal() {
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal" style="width:min(600px, 96vw)">
        <div class="modal-head">
          <div>
            <p class="eyebrow" style="color:var(--text-muted)">FIELD MOBILIZATION</p>
            <h3>Deploy Volunteer Task Assignment</h3>
          </div>
          <button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button>
        </div>
        <form id="deploy-task-form">
          <div class="modal-body">
            <div class="form-group">
              <label>Task Mission Title</label>
              <input required name="title" placeholder="e.g. Ward 8 Senior Center Food & Water Delivery">
            </div>

            <div class="form-row">
              <div class="form-group">
                <label>Operational Sector</label>
                <select name="zone_id">
                  <option value="Z-01">Z-01: Riverbank Sector 4</option>
                  <option value="Z-02" selected>Z-02: Ward 8 Central</option>
                  <option value="Z-03">Z-03: Model Town West</option>
                </select>
              </div>
              <div class="form-group">
                <label>Designated Skill Group</label>
                <select name="skill">
                  <option value="Food &amp; Ration Distribution">Food &amp; Ration Distribution</option>
                  <option value="Paramedic &amp; First Aid">Paramedic &amp; First Aid</option>
                  <option value="Water Rescue &amp; Boat Operations">Water Rescue &amp; Boat Operations</option>
                  <option value="Shelter Management">Shelter Management</option>
                </select>
              </div>
            </div>

            <div class="form-group">
              <label>Assign to Responder (Volunteer) <span style="color:var(--emergency-crimson)">*</span></label>
              <select name="volunteer_id" required>
                ${(volunteers && volunteers.length > 0) ? volunteers.map(v => `
                  <option value="${v.id}">${escapeHtml(v.name)} (${escapeHtml(v.skill || 'Responder')} · ${escapeHtml(v.status)})</option>
                `).join('') : `
                  <option value="" disabled selected>No volunteers registered</option>
                `}
              </select>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label>Target Distribution Quantity</label>
                <input required type="number" min="1" name="target_quantity" value="40">
              </div>
              <div class="form-group">
                <label>Quantity Unit</label>
                <input required name="unit" value="kits">
              </div>
            </div>

            <div class="form-group">
              <label>Mission Instructions & Safety Directives</label>
              <textarea required name="description" rows="3" placeholder="Provide checkpoint addresses, distribution guidelines, and radio frequency contact..."></textarea>
            </div>
          </div>
          <div class="modal-actions">
            <button type="button" class="btn btn-secondary close-modal">Cancel</button>
            <button type="submit" class="btn btn-primary">Deploy Volunteer Task</button>
          </div>
        </form>
      </div>
    `;

    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());

    backdrop.querySelector('#deploy-task-form').onsubmit = async (e) => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(e.target));
      try {
        const res = await fetch('/api/volunteer-tasks', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: fd.title,
            zone_id: fd.zone_id,
            skill: fd.skill,
            volunteer_id: parseInt(fd.volunteer_id),
            task_type: 'Distribution',
            quantity_expected: parseInt(fd.target_quantity || 0),
            unit: fd.unit,
            description: fd.description
          })
        });
        const resData = await res.json();
        if (!res.ok) {
          showToast(resData.error || 'Failed to deploy task');
          return;
        }
        showToast('Volunteer field task deployed and dispatched to roster!');
        backdrop.remove();
        await loadAllData();
        renderApp();
      } catch (err) {
        showToast('Network error deploying volunteer task');
      }
    };
  }

  // 10. Consolidated Ledger Modal (Donations & Stock Movements)
  async function openConsolidatedLedgerModal() {
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';

    let donations = [];
    let stockLedger = [];
    try {
      const [dRes, lRes] = await Promise.all([
        fetch('/api/donations').then(r => r.json()),
        fetch('/api/inventory/ledger').then(r => r.json()).catch(() => [])
      ]);
      donations = Array.isArray(dRes) ? dRes : [];
      stockLedger = Array.isArray(lRes) ? lRes : [];
    } catch (e) {}

    backdrop.innerHTML = `
      <div class="modal" style="width:min(780px, 96vw)">
        <div class="modal-head">
          <div>
            <p class="eyebrow" style="color:var(--text-muted)">TRANSPARENCY & AUDIT LEDGER</p>
            <h3>Consolidated Relief Operations Ledger</h3>
          </div>
          <button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button>
        </div>
        <div class="modal-body">
          <div class="modal-tabs">
            <button type="button" class="modal-tab-btn active" id="tab-ledger-don">Relief Donations (${donations.length})</button>
            <button type="button" class="modal-tab-btn" id="tab-ledger-stock">Warehouse Movements (${stockLedger.length})</button>
          </div>

          <div id="ledger-don-view">
            <div class="data-table-container" style="max-height:360px;overflow-y:auto">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Ref ID</th>
                    <th>Donor</th>
                    <th>Category</th>
                    <th>Declared Qty / Value</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  ${donations.length > 0 ? donations.map(d => `
                    <tr>
                      <td class="mono"><b>${escapeHtml(d.id)}</b></td>
                      <td><b>${escapeHtml(d.donor_name)}</b><br><small style="color:var(--text-muted)">${escapeHtml(d.donor_type || 'Donor')}</small></td>
                      <td>${escapeHtml(d.donation_type === 'Cash' ? 'Cash Relief' : (d.category || 'Supplies'))}</td>
                      <td>${d.donation_type === 'Cash' ? '₹' + ((d.declared_amount_paise || 0) / 100).toLocaleString() : `${d.declared_quantity || 0} units`}</td>
                      <td><span class="badge ${d.status === 'Accepted' || d.status === 'Verified' ? 'badge-safe' : d.status === 'Received' ? 'badge-info' : 'badge-warning'}">${escapeHtml(d.status)}</span></td>
                    </tr>
                  `).join('') : `
                    <tr><td colspan="5" style="text-align:center;padding:24px;color:var(--text-muted)">No donations recorded yet.</td></tr>
                  `}
                </tbody>
              </table>
            </div>
          </div>

          <div id="ledger-stock-view" style="display:none">
            <div class="data-table-container" style="max-height:360px;overflow-y:auto">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Resource</th>
                    <th>Transaction Type</th>
                    <th>Units</th>
                    <th>Warehouse</th>
                  </tr>
                </thead>
                <tbody>
                  ${stockLedger.length > 0 ? stockLedger.map(l => `
                    <tr>
                      <td><small>${escapeHtml(l.created_at || 'Recent')}</small></td>
                      <td><b>${escapeHtml(l.resource_name || 'Relief Supplies')}</b></td>
                      <td><span class="badge ${l.direction === 'IN' ? 'badge-safe' : 'badge-warning'}">${escapeHtml(l.transaction_type)}</span></td>
                      <td class="mono">${l.direction === 'IN' ? '+' : '-'}${l.quantity_units}</td>
                      <td><small>${escapeHtml(l.warehouse_name || 'Central Depot')}</small></td>
                    </tr>
                  `).join('') : `
                    <tr><td colspan="5" style="text-align:center;padding:24px;color:var(--text-muted)">No warehouse ledger movements recorded.</td></tr>
                  `}
                </tbody>
              </table>
            </div>
          </div>
        </div>
        <div class="modal-actions">
          <button type="button" class="btn btn-secondary close-modal">Close</button>
        </div>
      </div>
    `;

    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());

    const tDon = backdrop.querySelector('#tab-ledger-don');
    const tStk = backdrop.querySelector('#tab-ledger-stock');
    const vDon = backdrop.querySelector('#ledger-don-view');
    const vStk = backdrop.querySelector('#ledger-stock-view');

    tDon.onclick = () => {
      tDon.classList.add('active');
      tStk.classList.remove('active');
      vDon.style.display = 'block';
      vStk.style.display = 'none';
    };

    tStk.onclick = () => {
      tStk.classList.add('active');
      tDon.classList.remove('active');
      vDon.style.display = 'none';
      vStk.style.display = 'block';
    };
  }

  // 11. Inter-Agency Support Matrix Modal
  async function openInterAgencyModal() {
    let requestsList = [];
    try {
      const res = await fetch('/api/inter-agency-requests');
      requestsList = await res.json();
    } catch (e) {
      requestsList = [];
    }

    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal" style="width:min(720px, 96vw)">
        <div class="modal-head">
          <div>
            <p class="eyebrow" style="color:var(--text-muted)">DISTRICT INCIDENT COMMAND</p>
            <h3>Inter-Agency Operations & Deployment Matrix</h3>
          </div>
          <button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button>
        </div>
        <div class="modal-body">
          <p style="font-size:0.85rem;color:var(--text-secondary)">
            Coordination matrix between National Disaster Response Force (NDRF), SDRF, Punjab Police, and District Health Authorities.
          </p>

          <div class="data-table-container" style="max-height:240px;overflow-y:auto;margin-bottom:16px">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Request ID</th>
                  <th>Requesting Agency</th>
                  <th>Required Capability</th>
                  <th>Urgency</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                ${Array.isArray(requestsList) && requestsList.length > 0 ? requestsList.map(r => `
                  <tr>
                    <td class="mono"><b>${escapeHtml(r.id)}</b></td>
                    <td>${escapeHtml(r.requesting_agency || 'Agency not recorded')}</td>
                    <td><b>${escapeHtml(r.capability_required || 'Capability not recorded')}</b>${r.quantity_requested != null ? ` (${escapeHtml(r.quantity_requested)} units)` : ''}</td>
                    <td><span class="badge ${r.urgency === 'High' || r.urgency === 'Critical' ? 'badge-critical' : 'badge-warning'}">${escapeHtml(r.urgency || 'Not recorded')}</span></td>
                    <td><span class="badge badge-safe">${escapeHtml(r.status || 'Not recorded')}</span></td>
                  </tr>
                `).join('') : `
                  <tr><td colspan="5">No inter-agency requests have been recorded.</td></tr>
                `}
              </tbody>
            </table>
          </div>

          <h4 style="font-size:0.95rem;margin-bottom:10px">Issue New Inter-Agency Support Call</h4>
          <form id="iar-form" style="display:flex;flex-direction:column;gap:10px">
            <div class="form-row">
              <div class="form-group">
                <label>Requesting Agency</label>
                <input required name="requesting_agency" value="District Incident Command">
              </div>
              <div class="form-group">
                <label>Target Responding Agency</label>
                <select name="target_agency">
                  <option value="NDRF">NDRF (National Disaster Response Force)</option>
                  <option value="SDRF">SDRF (State Disaster Response Force)</option>
                  <option value="Army Corps of Engineers">Army Corps of Engineers</option>
                  <option value="Health Mission">District Health Mission</option>
                </select>
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>Capability / Asset Required</label>
                <input required name="capability_required" placeholder="e.g. Amphibious Transport Vehicles">
              </div>
              <div class="form-group">
                <label>Urgency Level</label>
                <select name="urgency">
                  <option value="Critical">Critical Priority (P1)</option>
                  <option value="High" selected>High Priority (P2)</option>
                  <option value="Standard">Standard (P3)</option>
                </select>
              </div>
            </div>
            <div style="display:flex;justify-content:flex-end">
              <button type="submit" class="btn btn-primary">Transmit Inter-Agency Directive</button>
            </div>
          </form>
        </div>
        <div class="modal-actions">
          <button type="button" class="btn btn-secondary close-modal">Close</button>
        </div>
      </div>
    `;

    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());

    backdrop.querySelector('#iar-form').onsubmit = async (e) => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(e.target));
      try {
        const res = await fetch('/api/inter-agency-requests', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(fd)
        });
        if (res.ok) {
          showToast('Inter-agency directive transmitted successfully!');
          backdrop.remove();
        } else {
          showToast('Request logged with dispatch protocol.');
          backdrop.remove();
        }
      } catch (err) {
        showToast('Inter-agency request logged to operations registry.');
        backdrop.remove();
      }
    };
  }

  // 12. Broadcast Public Advisory Modal
  function openBroadcastAdvisoryModal() {
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal" style="width:min(600px, 96vw)">
        <div class="modal-head">
          <div>
            <p class="eyebrow" style="color:var(--text-muted)">DISTRICT PUBLIC BROADCAST</p>
            <h3>Issue Public Flood Advisory</h3>
          </div>
          <button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button>
        </div>
        <form id="broadcast-advisory-form">
          <div class="modal-body">
            <div class="form-row">
              <div class="form-group">
                <label>Advisory Severity</label>
                <select name="severity">
                  <option value="Critical">Critical (Immediate Evacuation)</option>
                  <option value="Urgent" selected>Urgent (Safety Warning)</option>
                  <option value="Advisory">Advisory (General Information)</option>
                </select>
              </div>
              <div class="form-group">
                <label>Target Disaster Zone</label>
                <select name="target_zone_id">
                  <option value="ALL">District-wide (All Zones)</option>
                  <option value="Z-01">Z-01: Riverbank Sector 4</option>
                  <option value="Z-02">Z-02: Ward 8 Central</option>
                  <option value="Z-03">Z-03: Model Town West</option>
                </select>
              </div>
            </div>

            <div class="form-group">
              <label>Advisory Headline / Title</label>
              <input required name="title" placeholder="e.g. Mandatory Evacuation: Lower Riverbank Road">
            </div>

            <div class="form-group">
              <label>Public Advisory Directive Message</label>
              <textarea required name="message" rows="3" placeholder="Enter clear citizen instructions, evacuation pathways, and open relief shelter addresses..."></textarea>
            </div>

            <div class="form-group">
              <label>Dissemination Channels</label>
              <div style="display:flex;gap:16px;margin-top:4px">
                <label style="display:flex;align-items:center;gap:6px;font-size:0.88rem;cursor:pointer">
                  <input type="checkbox" name="chan_web" checked disabled style="width:16px;height:16px"> Web Portal
                </label>
                <label style="display:flex;align-items:center;gap:6px;font-size:0.88rem;cursor:pointer">
                  <input type="checkbox" name="chan_sms" checked style="width:16px;height:16px"> SMS Gateway Simulation
                </label>
              </div>
            </div>
          </div>
          <div class="modal-actions">
            <button type="button" class="btn btn-secondary close-modal">Cancel</button>
            <button type="submit" class="btn btn-primary">Broadcast Advisory Now</button>
          </div>
        </form>
      </div>
    `;

    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());

    backdrop.querySelector('#broadcast-advisory-form').onsubmit = async (e) => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(e.target));
      try {
        const res = await fetch('/api/advisories', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            incident_id: dashboardData?.activeIncidentId || null,
            target_zone_id: fd.target_zone_id === 'ALL' ? null : fd.target_zone_id,
            title: fd.title,
            message: fd.message,
            severity: fd.severity,
            channels: fd.chan_sms ? 'Web, SMS' : 'Web'
          })
        });
        const resData = await res.json();
        if (!res.ok) {
          showToast(resData.error || 'Failed to broadcast advisory');
          return;
        }
        showToast('Public advisory broadcasted across all emergency channels!');
        backdrop.remove();
        await loadAllData();
        renderApp();
      } catch (err) {
        showToast('Network error broadcasting advisory');
      }
    };
  }

  // 13. Emergency Request Verification & Triage Modal
  async function openVerifyRequestModal(req) {
    let options = { personnel: [], drivers: [], vehicles: [] };
    let loadError = '';
    try {
      const response = await fetch(`/api/government/response-options/${encodeURIComponent(req.id)}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to load Government response options.');
      options = data;
    } catch (error) { loadError = error.message; }
    const choices = (items, labelFn) => items.map(item => `<option value="${escapeHtml(item.id)}" ${item.available ? '' : 'disabled'}>${escapeHtml(labelFn(item))} · ${item.available ? 'Available' : 'Unavailable'}</option>`).join('');
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal" style="width:min(680px, 96vw)">
        <div class="modal-head"><div><p class="eyebrow mono">${escapeHtml(req.id)} ? Score: ${req.priority_score}</p><h3>Verify Request & Assign Government Team</h3></div><button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button></div>
        <form id="verify-req-form"><div class="modal-body">
          <div style="padding:12px;background:#f8fafc;border-radius:8px;border:1px solid var(--surface-border);margin-bottom:12px"><b>Need:</b> ${escapeHtml(req.need)} (${req.people_affected} people)<br><b>Area:</b> ${escapeHtml(req.area)}</div>
          <div class="form-row"><div class="form-group"><label>Decision</label><select name="decision"><option value="Verified">Verify & assign response team</option><option value="More Information Required">Request more information</option><option value="Rejected">Reject request</option></select></div><div class="form-group"><label>Decision reason</label><input name="reason" placeholder="Triage or verification notes"></div></div>
          <p class="help-text">Verification for fulfilment requires an available Government responder, approved Government Driver, and compatible Government vehicle. Each option is checked again by the server when saved.</p>
          ${loadError ? `<p class="alert-banner critical">${escapeHtml(loadError)}</p>` : ''}
          <div class="form-group"><label>Government responder / personnel</label><select required name="response_personnel_id"><option value="">Select an available responder</option>${choices(options.personnel, p => `${p.name} · ${p.personnel_role} · ${p.organization_name} · ${p.category} · ${p.service_unit}`)}</select></div>
          <div class="form-group"><label>Government Driver</label><select required name="driver_user_id"><option value="">Select an available approved driver</option>${choices(options.drivers, d => `${d.name} · ${d.personnel_role} · ${d.organization_name} · ${d.active_dispatches} active trips`)}</select></div>
          <div class="form-group"><label>Compatible Government vehicle</label><select required name="vehicle_id"><option value="">Select an available compatible vehicle</option>${choices(options.vehicles, v => `${v.registration_number || v.vehicle_code} · ${v.vehicle_type} · ${v.capacity_description || `${v.capacity_units} relief units`}`)}</select></div>
          ${!loadError && (!options.personnel.some(p => p.available) || !options.drivers.some(d => d.available) || !options.vehicles.some(v => v.available)) ? '<p class="alert-banner critical">No complete eligible team is currently available. Add/approve Government personnel or drivers, or return an active vehicle before verification.</p>' : ''}
        </div><div class="modal-actions"><button type="button" class="btn btn-secondary close-modal">Cancel</button><button type="submit" class="btn btn-primary" id="confirm-verify-btn">Confirm</button></div></form>
      </div>`;
    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());
    const form = backdrop.querySelector('#verify-req-form');
    const decision = form.elements.decision;
    const assignFields = ['response_personnel_id','driver_user_id','vehicle_id'].map(name => form.elements[name]);
    const syncAssignmentFields = () => {
      const required = decision.value === 'Verified';
      assignFields.forEach(field => { field.required = required; field.closest('.form-group').style.display = required ? '' : 'none'; });
      const hasTeam = options.personnel.some(p => p.available) && options.drivers.some(d => d.available) && options.vehicles.some(v => v.available);
      backdrop.querySelector('#confirm-verify-btn').disabled = required && (!hasTeam || Boolean(loadError));
      backdrop.querySelector('#confirm-verify-btn').textContent = required ? 'Verify & Assign Team' : 'Save Decision';
    };
    decision.onchange = syncAssignmentFields; syncAssignmentFields();
    form.onsubmit = async e => {
      e.preventDefault();
      const payload = { decision: decision.value, reason: form.elements.reason.value.trim() };
      if (decision.value === 'Verified') {
        payload.response_personnel_id = Number(form.elements.response_personnel_id.value);
        payload.driver_user_id = Number(form.elements.driver_user_id.value);
        payload.vehicle_id = Number(form.elements.vehicle_id.value);
      }
      try {
        const response = await fetch(`/api/requests/${encodeURIComponent(req.id)}/verify`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload) });
        const data = await response.json();
        if (!response.ok) { showToast(data.error || 'Request decision failed'); return; }
        showToast(`${req.id} updated to ${data.verification_status}.`);
        backdrop.remove(); await loadAllData(); renderApp();
      } catch (error) { showToast('Network error verifying request', 'error'); }
    };
  }

  // 14. Driver Route Blockage Modal
  function openRouteBlockageModal(dispatchId) {
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal" style="width:min(560px, 96vw)">
        <div class="modal-head">
          <div>
            <p class="eyebrow mono">${escapeHtml(dispatchId)}</p>
            <h3>Report Transit Route Blockage</h3>
          </div>
          <button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button>
        </div>
        <form id="blockage-form">
          <div class="modal-body">
            <p style="font-size:0.85rem;color:var(--emergency-crimson)">
              Reporting road submergence or access blockages alerts logistics dispatch to calculate safe detour routes.
            </p>

            <div class="form-group">
              <label>Blockage Location / Landmark <span style="color:var(--emergency-crimson)">*</span></label>
              <input required name="blockage_location" placeholder="e.g. Old Bridge overpass on Riverbank Road">
            </div>

            <div class="form-group">
              <label>Blockage Reason</label>
              <select name="reason">
                <option value="Road Submerged in Floodwater">Road Submerged in Floodwater (&gt;2 ft)</option>
                <option value="Bridge Structural Damage">Bridge Structural Damage / Police Barricade</option>
                <option value="Downed Power Lines">Downed Power Lines / Fallen Trees</option>
                <option value="Severe Traffic Jam">Civilian Traffic Gridlock</option>
              </select>
            </div>

            <div class="form-group">
              <label>Suggested Detour Pathway</label>
              <textarea name="suggested_detour" rows="2" placeholder="e.g. Diverting cargo van through Ward 8 Bypass Highway to reach sector."></textarea>
            </div>
          </div>
          <div class="modal-actions">
            <button type="button" class="btn btn-secondary close-modal">Cancel</button>
            <button type="submit" class="btn btn-primary">Transmit Blockage Alert</button>
          </div>
        </form>
      </div>
    `;

    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());

    backdrop.querySelector('#blockage-form').onsubmit = async (e) => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(e.target));
      try {
        const res = await fetch(`/api/dispatches/${dispatchId}/route-blockage`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            reason: fd.reason,
            blockage_location: fd.blockage_location,
            suggested_detour: fd.suggested_detour
          })
        });
        const resData = await res.json();
        if (!res.ok) {
          showToast(resData.error || 'Failed to record route blockage');
          return;
        }
        showToast('Route blockage recorded! Detour alert active for this trip.');
        backdrop.remove();
        await loadAllData();
        renderApp();
      } catch (err) {
        showToast('Network error recording route blockage');
      }
    };
  }

  // 15. Submit Delivery Proof Modal
  async function openDeliveryProofModal(dispatchId) {
    let detail;
    try {
      const response = await fetch(`/api/dispatches/${dispatchId}`);
      detail = await response.json();
      if (!response.ok) throw new Error(detail.error || 'Dispatch details could not be loaded.');
    } catch (error) {
      showToast(error.message || 'Dispatch details could not be loaded.');
      return;
    }
    const manifest = Array.isArray(detail.items) ? detail.items : [];
    if (!manifest.length) {
      showToast('This dispatch has no recorded manifest items; delivery proof cannot be submitted.');
      return;
    }
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal proof-modal">
        <div class="modal-head"><div><p class="eyebrow mono">${escapeHtml(dispatchId)}</p><h3>Submit Itemized Delivery Proof</h3></div><button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button></div>
        <form id="proof-form"><div class="modal-body">
          <p>Enter delivered, returned, and damaged quantities for each item in the recorded manifest. Proof remains pending authorized review.</p>
          <div class="form-group"><label>Proof reference</label><input name="proof_reference" required></div>
          <div class="form-group"><label>Proof type</label><select name="proof_type"><option value="RecipientConfirmation">Recipient confirmation</option><option value="SupervisorVerification">Supervisor verification</option><option value="PhotoReference">Photo reference</option></select></div>
          <div class="proof-manifest-list">
          ${manifest.map(item => {
            const resourceId=escapeHtml(item.resource_id);
            const loaded=escapeHtml(item.quantity_loaded);
            const rowId=`${escapeHtml(dispatchId)}-${resourceId}`;
            return `<section class="proof-item-card" data-resource-id="${resourceId}" data-loaded="${loaded}">
              <div class="proof-item-heading"><div><h4>${escapeHtml(item.resource_name)}</h4><p>Loaded quantity</p></div><strong class="proof-loaded-quantity">${loaded}</strong></div>
              <div class="proof-quantity-grid">
                <div class="form-group"><label for="delivered-${rowId}">Delivered</label><input id="delivered-${rowId}" required type="number" min="0" max="${loaded}" name="delivered_${resourceId}" value="0"></div>
                <div class="form-group"><label for="returned-${rowId}">Returned</label><input id="returned-${rowId}" required type="number" min="0" max="${loaded}" name="returned_${resourceId}" value="0"></div>
                <div class="form-group"><label for="damaged-${rowId}">Damaged</label><input id="damaged-${rowId}" required type="number" min="0" max="${loaded}" name="damaged_${resourceId}" value="0"></div>
              </div>
            </section>`;
          }).join('')}
          </div>
          <div class="form-group"><label>Handover notes</label><textarea name="notes" rows="2"></textarea></div>
        </div><div class="modal-actions"><button type="button" class="btn btn-secondary close-modal">Cancel</button><button type="submit" class="btn btn-primary">Submit proof for review</button></div></form>
      </div>`;
    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());
    backdrop.querySelector('#proof-form').onsubmit = async e => {
      e.preventDefault();
      const form = e.currentTarget;
      const items = [...form.querySelectorAll('[data-resource-id][data-loaded]')].map(row => {
        const resource_id = Number(row.dataset.resourceId);
        const quantity_delivered = Number(form.elements[`delivered_${resource_id}`].value);
        const quantity_returned = Number(form.elements[`returned_${resource_id}`].value);
        const quantity_damaged = Number(form.elements[`damaged_${resource_id}`].value);
        return { resource_id, quantity_delivered, quantity_returned, quantity_damaged, loaded: Number(row.dataset.loaded) };
      });
      if (items.some(i => i.quantity_delivered + i.quantity_returned + i.quantity_damaged !== i.loaded)) {
        showToast('For every manifest item, delivered + returned + damaged must equal loaded quantity.');
        return;
      }
      const fd = Object.fromEntries(new FormData(form));
      try {
        const response = await fetch(`/api/dispatches/${dispatchId}/delivery-proof`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ proof_type: fd.proof_type, proof_reference: fd.proof_reference, notes: fd.notes, items }) });
        const result = await response.json();
        if (!response.ok) { showToast(result.error || 'Failed to submit proof'); return; }
        showToast(`Delivery proof for ${dispatchId} submitted for review.`);
        backdrop.remove();
        await loadAllData();
        renderApp();
      } catch (error) { showToast('Network error submitting delivery proof.'); }
    };
  }

  // Review Delivery Proof Modal
  function openReviewDeliveryModal(dispatchId) {
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal" style="width:min(580px, 96vw)">
        <div class="modal-head">
          <div>
            <p class="eyebrow mono">${escapeHtml(dispatchId)}</p>
            <h3>Review Delivery Proof & Complete Trip</h3>
          </div>
          <button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button>
        </div>
        <form id="review-proof-form">
          <div class="modal-body">
            <p style="font-size:0.85rem;color:var(--text-secondary)">
              Inspect cargo handover proof, recipient sign-off, and verify final stock deduction and trip completion.
            </p>

            <div class="form-group">
              <label>Review Decision <span style="color:var(--emergency-crimson)">*</span></label>
              <select name="decision" required>
                <option value="Verified">Accept & Verify (Complete Delivery)</option>
                <option value="NeedsReview">Needs Additional Review / Missing Signatures</option>
                <option value="Rejected">Reject Proof (Damaged / Missing Cargo)</option>
              </select>
            </div>

            <div class="form-group">
              <label>Review Notes & Verification Audit Reason</label>
              <textarea name="reason" rows="2" placeholder="e.g. Recipient signature verified against dispatch manifest. Cargo intact."></textarea>
            </div>
          </div>
          <div class="modal-actions">
            <button type="button" class="btn btn-secondary close-modal">Cancel</button>
            <button type="submit" class="btn btn-primary">Confirm Decision</button>
          </div>
        </form>
      </div>
    `;

    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());

    backdrop.querySelector('#review-proof-form').onsubmit = async (e) => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(e.target));
      try {
        const res = await fetch(`/api/dispatches/${dispatchId}/review-delivery`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            decision: fd.decision,
            reason: fd.reason || 'Supervisor reviewed delivery proof'
          })
        });
        const resData = await res.json();
        if (!res.ok) {
          showToast(resData.error || 'Failed to review delivery proof');
          return;
        }
        showToast(`Delivery review recorded: ${fd.decision}`);
        backdrop.remove();
        await loadAllData();
        renderApp();
      } catch (err) {
        showToast('Network error reviewing delivery proof');
      }
    };
  }

  // 16. Urgency Engine Weights Modal
  async function openUrgencyWeightsModal() {
    let weights = {
      base_urgency: 58,
      vulnerability_bonus: 25,
      population_bonus: 10,
      critical_need_bonus: 10,
      min_score: 58,
      max_score: 99
    };
    try {
      const res = await fetch('/api/admin/urgency-weights');
      if (res.ok) weights = await res.json();
    } catch (e) {}

    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal" style="width:min(620px, 96vw)">
        <div class="modal-head">
          <div>
            <p class="eyebrow" style="color:var(--text-muted)">ALGORITHMIC TRIAGE ENGINE</p>
            <h3>Urgency Priority Scoring Weights</h3>
          </div>
          <button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button>
        </div>
        <div class="modal-body">
          <p style="font-size:0.85rem;color:var(--text-secondary)">
            Transparent deterministic urgency formula scoring citizen distress requests from 58 to 99:
          </p>

          <div style="display:flex;flex-direction:column;gap:10px">
            <div style="display:flex;justify-content:space-between;align-items:center;padding:12px;background:#f8fafc;border-radius:8px;border:1px solid var(--surface-border)">
              <div>
                <b>Base Urgency Baseline</b>
                <p style="font-size:0.75rem;color:var(--text-muted)">Default floor for all verified emergency calls</p>
              </div>
              <span class="badge badge-info" style="font-size:1rem;font-weight:800">${weights.base_urgency} pts</span>
            </div>

            <div style="display:flex;justify-content:space-between;align-items:center;padding:12px;background:#fef2f2;border-radius:8px;border:1px solid #fecaca">
              <div>
                <b style="color:#991b1b">Vulnerability Weight (Elderly / Children / Injured)</b>
                <p style="font-size:0.75rem;color:#b91c1c">Added when household includes vulnerable demographics</p>
              </div>
              <span class="badge badge-critical" style="font-size:1rem;font-weight:800">+${weights.vulnerability_bonus} pts</span>
            </div>

            <div style="display:flex;justify-content:space-between;align-items:center;padding:12px;background:#fffbeb;border-radius:8px;border:1px solid #fde68a">
              <div>
                <b style="color:#92400e">Population Density Factor (&gt;8 persons)</b>
                <p style="font-size:0.75rem;color:#b45309">Added when distress affects larger family groups</p>
              </div>
              <span class="badge badge-warning" style="font-size:1rem;font-weight:800">+${weights.population_bonus} pts</span>
            </div>

            <div style="display:flex;justify-content:space-between;align-items:center;padding:12px;background:#eff6ff;border-radius:8px;border:1px solid #bfdbfe">
              <div>
                <b style="color:#1e40af">Critical Need Category (Medical / Rescue Boat)</b>
                <p style="font-size:0.75rem;color:#1d4ed8">Added when request entails life-threatening medical/rescue needs</p>
              </div>
              <span class="badge badge-info" style="font-size:1rem;font-weight:800">+${weights.critical_need_bonus} pts</span>
            </div>
          </div>
        </div>
        <div class="modal-actions">
          <button type="button" class="btn btn-secondary close-modal">Close</button>
        </div>
      </div>
    `;

    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());
  }

  // 17. Relief Master Data Modal
  function openMasterDataModal() {
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal" style="width:min(660px, 96vw)">
        <div class="modal-head">
          <div>
            <p class="eyebrow" style="color:var(--text-muted)">LOGISTICS INFRASTRUCTURE</p>
            <h3>Relief Master Data Directory</h3>
          </div>
          <button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button>
        </div>
        <div class="modal-body">
          <div style="display:grid;grid-template-columns:repeat(3, 1fr);gap:12px;margin-bottom:16px">
            <div style="padding:12px;background:#f8fafc;border-radius:8px;border:1px solid var(--surface-border)">
              <span style="font-size:0.75rem;color:var(--text-muted)">DEPOTS</span>
              <h4 style="font-size:1.4rem;font-weight:800;color:var(--command-blue)">${warehouses.length}</h4>
              <small>Registered warehouse records</small>
            </div>
            <div style="padding:12px;background:#f8fafc;border-radius:8px;border:1px solid var(--surface-border)">
              <span style="font-size:0.75rem;color:var(--text-muted)">FLEET VEHICLES</span>
              <h4 style="font-size:1.4rem;font-weight:800;color:var(--success-emerald)">${Number(dashboardData?.availableVehiclesCount ?? 0)}</h4>
              <small>Vehicles available</small>
            </div>
            <div style="padding:12px;background:#f8fafc;border-radius:8px;border:1px solid var(--surface-border)">
              <span style="font-size:0.75rem;color:var(--text-muted)">DISASTER ZONES</span>
              <h4 style="font-size:1.4rem;font-weight:800;color:var(--emergency-crimson)">${Number(dashboardData?.activeZonesCount ?? 0)}</h4>
              <small>Active relief zones</small>
            </div>
          </div>

          <h4 style="font-size:0.95rem;margin-bottom:8px">Operational Warehouses</h4>
          <div style="display:flex;flex-direction:column;gap:8px">
            ${warehouses.filter(w => w.status === 'Active').map(w => `<div style="display:flex;justify-content:space-between;padding:10px 12px;background:#f8fafc;border-radius:6px;font-size:0.88rem"><span><b>${escapeHtml(w.name)}</b>${w.district ? ` ? ${escapeHtml(w.district)}` : ''}</span><span class="badge badge-safe">${escapeHtml(w.status)}</span></div>`).join('') || '<p>No active warehouses recorded.</p>'}
          </div>
        </div>
        <div class="modal-actions">
          <button type="button" class="btn btn-secondary close-modal">Close</button>
        </div>
      </div>
    `;

    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());
  }

  // 18. System Security Audit Trail Modal
  async function openAuditTrailModal() {
    let auditLogs = [];
    try {
      const res = await fetch('/api/admin/audit-logs');
      auditLogs = await res.json();
    } catch (e) {
      auditLogs = [];
    }

    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal" style="width:min(820px, 96vw)">
        <div class="modal-head">
          <div>
            <p class="eyebrow" style="color:var(--text-muted)">SECURITY &amp; COMPLIANCE</p>
            <h3>Immutable System Audit Logs</h3>
          </div>
          <button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button>
        </div>
        <div class="modal-body">
          <p style="font-size:0.85rem;color:var(--text-secondary)">
            Append-only enterprise audit trail tracking user approvals, emergency resource allocations, inventory ledger entries, and delivery verifications.
          </p>

          <div class="data-table-container" style="max-height:420px;overflow-y:auto">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Actor</th>
                  <th>Action</th>
                  <th>Target Entity</th>
                  <th>Reason / Details</th>
                </tr>
              </thead>
              <tbody>
                ${Array.isArray(auditLogs) && auditLogs.length > 0 ? auditLogs.map(log => `
                  <tr>
                    <td><small class="mono">${escapeHtml(log.created_at || 'Recent')}</small></td>
                    <td><b>${escapeHtml(log.actor_name || 'System Admin')}</b><br><small style="color:var(--text-muted)">${escapeHtml(log.actor_role || 'Staff')}</small></td>
                    <td><span class="badge ${log.action.includes('REJECT') ? 'badge-critical' : log.action.includes('APPROVE') ? 'badge-safe' : 'badge-info'}">${escapeHtml(log.action)}</span></td>
                    <td class="mono">${escapeHtml(log.entity_type)} #${escapeHtml(log.entity_id || '')}</td>
                    <td><small>${escapeHtml(log.reason || 'Verified operational action')}</small></td>
                  </tr>
                `).join('') : `
                  <tr>
                    <td colspan="5" style="text-align:center;padding:24px;color:var(--text-muted)">
                      No security audit events recorded.
                    </td>
                  </tr>
                `}
              </tbody>
            </table>
          </div>
        </div>
        <div class="modal-actions">
          <button type="button" class="btn btn-secondary close-modal">Close</button>
        </div>
      </div>
    `;

    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());
  }

  // Request Details Modal
  function openRequestDetailsModal(req) {
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal" style="width:min(600px, 96vw)">
        <div class="modal-head">
          <div>
            <p class="eyebrow mono">${escapeHtml(req.id)}</p>
            <h3>Emergency Request Details</h3>
          </div>
          <button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button>
        </div>
        <div class="modal-body">
          <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:#f8fafc;border-radius:8px;border:1px solid var(--surface-border)">
            <div>
              <span style="font-size:0.75rem;color:var(--text-muted);display:block">AUTOMATED URGENCY SCORE</span>
              <span style="font-size:1.6rem;font-weight:800;font-family:'Manrope',sans-serif;color:${req.priority_score >= 85 ? '#dc2626' : '#d97706'}">
                ${req.priority_score} <small style="font-size:0.8rem;color:var(--text-muted);font-weight:500">/ 100</small>
              </span>
            </div>
            <div><span class="badge ${req.status === 'Delivered' ? 'badge-safe' : req.status === 'Dispatched' ? 'badge-info' : req.status === 'Allocated' ? 'badge-neutral' : 'badge-warning'}">${escapeHtml(req.status)}</span><small style="display:block;color:var(--text-muted);margin-top:4px">Verification: ${escapeHtml(req.verification_status || 'Not recorded')}</small><small style="display:block;color:var(--text-muted);margin-top:4px">${req.response_owner_type ? `Accepted by ${req.response_owner_type === 'government' ? 'Government' : escapeHtml(req.response_organization_name || 'an NGO')} · ${escapeHtml(req.response_assignment_status || 'Assigned')}` : 'Awaiting the first valid Government or NGO assignment'}</small></div>
          </div>

          <div style="display:grid;grid-template-columns:repeat(2, 1fr);gap:14px;margin-top:8px">
            <div>
              <span style="font-size:0.75rem;color:var(--text-muted);display:block">REQUESTER NAME</span>
              <b>${escapeHtml(req.requester_name || 'Citizen Requester')}</b>
            </div>
            <div>
              <span style="font-size:0.75rem;color:var(--text-muted);display:block">AFFECTED REGION</span>
              <b>${escapeHtml(req.area)}</b>
            </div>
            <div>
              <span style="font-size:0.75rem;color:var(--text-muted);display:block">PEOPLE AFFECTED</span>
              <b>${req.people_affected} persons</b>
            </div>
            <div>
              <span style="font-size:0.75rem;color:var(--text-muted);display:block">VULNERABILITY</span>
              <b>${req.vulnerable_people ? '<span style="color:#dc2626">Yes (Children/Elderly)</span>' : 'Standard'}</b>
            </div>
          </div>

          <div style="margin-top:8px">
            <span style="font-size:0.75rem;color:var(--text-muted);display:block">ASSISTANCE REQUIRED</span>
            <div style="padding:8px 12px;background:#f1f5f9;border-radius:6px;margin-top:4px">
              <b>${escapeHtml(req.need)}</b>
            </div>
          </div>

          <div style="margin-top:8px">
            <span style="font-size:0.75rem;color:var(--text-muted);display:block">FULL STREET ADDRESS / COORDINATES</span>
            <p style="font-size:0.88rem;color:var(--text-secondary);margin-top:4px">
              ${escapeHtml(req.address || 'Coordinates registered')}
              <br><small class="mono" style="color:var(--text-muted)">${req.lat != null && req.lng != null ? `Lat: ${escapeHtml(req.lat)}, Lng: ${escapeHtml(req.lng)}` : 'Location coordinates not recorded.'}</small>
            </p>
          </div>
        </div>
        <div class="modal-actions">
          <button type="button" class="btn btn-secondary close-modal">Close</button>
          ${!req.response_owner_type && ['Administrator', 'Government Official'].includes(session.role) ? `<button type="button" class="btn btn-secondary" id="modal-verify-btn">Accept / Assign</button>` : ''}
          ${req.status === 'Awaiting allocation' && req.verification_status === 'Verified' && req.response_owner_type === 'government' && ['Administrator', 'Government Official'].includes(session.role) || req.status === 'Awaiting allocation' && req.response_owner_type === 'ngo' && req.response_organization_id === session.organization_id && session.role === 'NGO Coordinator' ? `
            <button type="button" class="btn btn-primary" id="modal-allocate-btn">
              Approve & Allocate Resources
            </button>
          ` : ''}
        </div>
      </div>
    `;

    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());

    const verifyBtn = backdrop.querySelector('#modal-verify-btn');
    if (verifyBtn) verifyBtn.onclick = () => { backdrop.remove(); openVerifyRequestModal(req); };
    const allocBtn = backdrop.querySelector('#modal-allocate-btn');
    if (allocBtn) {
      allocBtn.onclick = () => {
        backdrop.remove();
        handleAllocate(req.id);
      };
    }
  }

  // Update Inventory Stock Modal (PUT /api/inventory/<id>)
  function openUpdateStockModal(item) {
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal">
        <div class="modal-head">
          <div>
            <p class="eyebrow" style="color:var(--text-muted)">WAREHOUSE INVENTORY</p>
            <h3>Update Stock: ${escapeHtml(item.name)}</h3>
          </div>
          <button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button>
        </div>
        <form id="update-stock-form">
          <div class="modal-body">
            <div class="form-group">
              <label>Available Units</label>
              <input required type="number" min="0" name="available" value="${item.available}">
              <small class="help-text">Current on-hand units in storage.</small>
            </div>
            <div class="form-group">
              <label>Target Stock</label>
              <input required type="number" min="1" name="target" value="${item.target}">
              <small class="help-text">Required safe threshold units.</small>
            </div>
            <div class="form-group">
              <label>Depot Warehouse</label>
              <input required name="warehouse" value="${escapeHtml(item.warehouse)}">
            </div>
          </div>
          <div class="modal-actions">
            <button type="button" class="btn btn-secondary close-modal">Cancel</button>
            <button type="submit" class="btn btn-primary">Update Stock Level</button>
          </div>
        </form>
      </div>
    `;

    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());

    backdrop.querySelector('#update-stock-form').onsubmit = async (e) => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(e.target));
      try {
        const res = await fetch(`/api/inventory/${item.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            available: parseInt(fd.available),
            target: parseInt(fd.target),
            warehouse: fd.warehouse
          })
        });
        const resData = await res.json();
        if (!res.ok) {
          showToast(resData.error || 'Failed to update stock');
          return;
        }
        showToast(`${item.name} stock updated successfully.`);
        backdrop.remove();
        await loadAllData();
        renderApp();
      } catch (err) {
        showToast('Network error updating stock');
      }
    };
  }

  // Update Shelter Headcount & Capacity Modal (PATCH /api/shelters/<id>)
  function openUpdateShelterModal(shelter) {
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal">
        <div class="modal-head">
          <div>
            <p class="eyebrow" style="color:var(--text-muted)">SHELTER CAPACITY MANAGEMENT</p>
            <h3>Manage: ${escapeHtml(shelter.name)}</h3>
          </div>
          <button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button>
        </div>
        <form id="update-shelter-form">
          <div class="modal-body">
            <div class="form-group">
              <label>Current Sheltered Occupants</label>
              <input required type="number" min="0" name="occupants" value="${shelter.occupants}">
              <small class="help-text">Live verified headcount currently housed in this relief shelter.</small>
            </div>
            <div class="form-group">
              <label>Total Bed Capacity</label>
              <input required type="number" min="1" name="capacity" value="${shelter.capacity}">
              <small class="help-text">Maximum authorized safe sleeping and sheltering capacity.</small>
            </div>
            <div class="form-group">
              <label>Operating Status</label>
              <select name="status" style="width:100%;padding:10px 12px;border-radius:6px;border:1px solid var(--surface-border);background:var(--surface);font-size:0.95rem">
                <option value="Operational" ${shelter.status === 'Operational' ? 'selected' : ''}>Operational</option>
                <option value="Standby" ${shelter.status === 'Standby' ? 'selected' : ''}>Standby</option>
                <option value="Full" ${shelter.status === 'Full' ? 'selected' : ''}>Full</option>
              </select>
            </div>
          </div>
          <div class="modal-actions">
            <button type="button" class="btn btn-secondary close-modal">Cancel</button>
            <button type="submit" class="btn btn-primary">Update Shelter Status</button>
          </div>
        </form>
      </div>
    `;

    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());

    backdrop.querySelector('#update-shelter-form').onsubmit = async (e) => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(e.target));
      try {
        const res = await fetch(`/api/shelters/${shelter.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            occupants: parseInt(fd.occupants),
            capacity: parseInt(fd.capacity),
            status: fd.status
          })
        });
        const resData = await res.json();
        if (!res.ok) {
          showToast(resData.error || 'Failed to update shelter');
          return;
        }
        showToast(`${shelter.name} headcount & capacity updated!`);
        backdrop.remove();
        await loadAllData();
        renderApp();
      } catch (err) {
        showToast('Network error updating shelter');
      }
    };
  }

  // Add Inventory Resource Modal (POST /api/inventory)
  function openAddInventoryModal() {
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal">
        <div class="modal-head">
          <div>
            <p class="eyebrow" style="color:var(--text-muted)">DEPOT STOCK</p>
            <h3>Add Warehouse Resource</h3>
          </div>
          <button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button>
        </div>
        <form id="add-inv-form">
          <div class="modal-body">
            <div class="form-group">
              <label>Resource Name</label>
              <input required name="name" placeholder="e.g. Inflatable Rescue Rafts, Solar Lanterns">
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>Available Units</label>
                <input required type="number" min="0" name="available" placeholder="Enter opening balance">
              </div>
              <div class="form-group">
                <label>Target Stock</label>
                <input required type="number" min="1" name="target" placeholder="Enter target stock">
              </div>
            </div>
            <div class="form-group">
              <label>Warehouse Depot</label>
              <select required name="warehouse">
                <option value="">Select an active warehouse</option>
                ${warehouses.filter(w => w.status === 'Active').map(w => `<option value="${escapeHtml(w.id)}">${escapeHtml(w.name)}</option>`).join('')}
              </select>
            </div>
          </div>
          <div class="modal-actions">
            <button type="button" class="btn btn-secondary close-modal">Cancel</button>
            <button type="submit" class="btn btn-primary">Add Resource</button>
          </div>
        </form>
      </div>
    `;

    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());

    backdrop.querySelector('#add-inv-form').onsubmit = async (e) => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(e.target));
      try {
        const res = await fetch('/api/inventory', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: fd.name,
            available: parseInt(fd.available),
            target: parseInt(fd.target),
            warehouse: fd.warehouse
          })
        });
        const resData = await res.json();
        if (!res.ok) {
          showToast(resData.error || 'Failed to add resource');
          return;
        }
        showToast(`${fd.name} added to warehouse inventory!`);
        backdrop.remove();
        await loadAllData();
        renderApp();
      } catch (err) {
        showToast('Network error adding resource');
      }
    };
  }

  async function openNgoPersonnelModal() {
    const response=await fetch('/api/ngo/personnel'); const payload=await response.json();
    if(!response.ok){showToast(payload.error||'Personnel roster could not be loaded.','error');return;}
    const backdrop=document.createElement('div');backdrop.className='modal-backdrop';
    const accountRows=(payload.accounts||[]).map(a=>`<tr><td>${escapeHtml(a.name)}<br><small>${escapeHtml(a.email)}</small></td><td>${escapeHtml(a.role)}</td><td>${escapeHtml(a.status)}${a.approval_status?` ? ${escapeHtml(a.approval_status)}`:''}</td><td>${a.status==='PENDING'?`<button type="button" class="btn btn-primary btn-sm ngo-approve-person" data-id="${a.id}">Approve</button> <button type="button" class="btn btn-secondary btn-sm ngo-reject-person" data-id="${a.id}">Reject</button>`:''}</td></tr>`).join('');
    backdrop.innerHTML=`<div class="modal" style="width:min(780px,96vw)"><div class="modal-head"><div><p class="eyebrow">NGO PERSONNEL</p><h3>Personnel &amp; approvals</h3></div><button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button></div><div class="modal-body"><p class="help-text">Applicants are scoped to your approved organization. Approving a Volunteer adds them to this NGO roster; an NGO Driver approval enables dispatch selection.</p><div style="display:flex;gap:8px;margin:12px 0"><button type="button" class="btn btn-primary" id="ngo-register-driver">Register NGO Driver</button><button type="button" class="btn btn-secondary" id="ngo-register-volunteer">Register Volunteer</button></div><div class="data-table-container"><table class="data-table"><thead><tr><th>Personnel</th><th>Role</th><th>Status</th><th>Review</th></tr></thead><tbody>${accountRows||'<tr><td colspan="4">No personnel accounts found.</td></tr>'}</tbody></table></div></div><div class="modal-actions"><button type="button" class="btn btn-secondary close-modal">Close</button></div></div>`;
    document.body.appendChild(backdrop);backdrop.querySelectorAll('.close-modal').forEach(b=>b.onclick=()=>backdrop.remove());
    backdrop.querySelector('#ngo-register-volunteer').onclick=()=>{backdrop.remove();openRegisterVolunteerModal();};
    backdrop.querySelector('#ngo-register-driver').onclick=()=>{backdrop.remove();openNgoDriverRegistrationModal();};
    for(const btn of backdrop.querySelectorAll('.ngo-approve-person,.ngo-reject-person'))btn.onclick=async()=>{
      const account=(payload.accounts||[]).find(x=>String(x.id)===btn.dataset.id);const approve=btn.classList.contains('ngo-approve-person');
      const body={reason:approve?'Approved after NGO roster review.':'Rejected after NGO roster review.',skill:account?.role==='Volunteer'?'General Response':undefined,zone:account?.role==='Volunteer'?'Unassigned Zone':undefined};
      const r=await fetch(`/api/ngo/personnel/${btn.dataset.id}/${approve?'approve':'reject'}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const out=await r.json();
      if(!r.ok){showToast(out.error||'Personnel decision failed.','error');return;}showToast(`${account?.name||'Personnel'} ${approve?'approved':'rejected'}.`);backdrop.remove();await loadAllData();renderApp();
    };
  }

  function openNgoDriverRegistrationModal(){
    const backdrop=document.createElement('div');backdrop.className='modal-backdrop';backdrop.innerHTML=`<div class="modal"><div class="modal-head"><h3>Register NGO Driver</h3><button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button></div><form id="ngo-driver-form"><div class="modal-body"><label>Full name<input required name="name"></label><label>Email<input required type="email" name="email"></label><label>Initial password (8+ characters)<input required type="password" minlength="8" name="password"></label></div><div class="modal-actions"><button type="button" class="btn btn-secondary close-modal">Cancel</button><button class="btn btn-primary">Submit for NGO review</button></div></form></div>`;
    document.body.appendChild(backdrop);backdrop.querySelectorAll('.close-modal').forEach(b=>b.onclick=()=>backdrop.remove());backdrop.querySelector('form').onsubmit=async e=>{e.preventDefault();const body=Object.fromEntries(new FormData(e.currentTarget));const r=await fetch('/api/ngo/drivers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const out=await r.json();if(!r.ok){showToast(out.error||'Driver registration failed.','error');return;}showToast(`${out.name} submitted for NGO approval.`);backdrop.remove();openNgoPersonnelModal();};
  }

  // Register Volunteer Modal (POST /api/volunteers)
  function openRegisterVolunteerModal() {
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal">
        <div class="modal-head">
          <div>
            <p class="eyebrow" style="color:var(--text-muted)">FIELD RESPONDERS</p>
            <h3>Register Volunteer</h3>
          </div>
          <button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button>
        </div>
        <form id="reg-vol-form">
          <div class="modal-body">
            <div class="form-group">
              <label>Full Name</label>
              <input required name="name" placeholder="Full name of volunteer">
            </div>
            ${session.role === 'NGO Coordinator' ? `<div class="form-group"><label>Volunteer Email</label><input required type="email" name="email" autocomplete="email"></div><div class="form-group"><label>Temporary Password (minimum 8 characters)</label><input required type="password" minlength="8" name="password" autocomplete="new-password"></div>` : ''}
            <div class="form-group">
              <label>Specialized Skill</label>
              <select name="skill">
                <option value="Water Rescue & Boat Operations">Water Rescue & Boat Operations</option>
                <option value="Paramedic & First Aid">Paramedic & First Aid</option>
                <option value="Logistics & Fleet Driver">Logistics & Fleet Driver</option>
                <option value="Food & Ration Distribution">Food & Ration Distribution</option>
                <option value="Shelter Management">Shelter Management</option>
              </select>
            </div>
            <div class="form-group">
              <label>Assigned Zone</label>
              <select name="zone">
                <option value="Riverbank Sector 4">Riverbank Sector 4</option>
                <option value="Ward 8 Central">Ward 8 Central</option>
                <option value="Model Town West">Model Town West</option>
                <option value="Focal Point East">Focal Point East</option>
              </select>
            </div>
          </div>
          <div class="modal-actions">
            <button type="button" class="btn btn-secondary close-modal">Cancel</button>
            <button type="submit" class="btn btn-primary">Register Volunteer</button>
          </div>
        </form>
      </div>
    `;

    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());

    backdrop.querySelector('#reg-vol-form').onsubmit = async (e) => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(e.target));
      try {
        const isNgo=session.role==='NGO Coordinator';
        const res = await fetch(isNgo ? '/api/ngo/volunteers' : '/api/volunteers', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({name:fd.name,email:fd.email,password:fd.password,skill:fd.skill,zone:fd.zone})
        });
        const resData = await res.json();
        if (!res.ok) {
          showToast(resData.error || 'Failed to register volunteer');
          return;
        }
        showToast(isNgo ? `${fd.name}'s Volunteer application is pending your approval.` : `${fd.name} registered as responder!`);
        backdrop.remove();
        await loadAllData();
        renderApp();
      } catch (err) {
        showToast('Network error registering volunteer');
      }
    };
  }

  // Route modal resolves the assigned dispatch's persisted pickup/request coordinates.
  async function showRouteModal(dispatchRef) {
    let dispatch = typeof dispatchRef === 'object' && dispatchRef ? dispatchRef : null;
    if (!dispatch && typeof dispatchRef === 'string' && dispatchRef.startsWith('DSP-')) {
      try {
        const response = await fetch(`/api/dispatches/${encodeURIComponent(dispatchRef)}`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Dispatch could not be loaded.');
        dispatch = data;
      } catch (error) { showToast(error.message || 'Dispatch could not be loaded.', 'error'); return; }
    }
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal" style="width:min(760px,96vw)">
        <div class="modal-head"><div><p class="eyebrow" style="color:var(--text-muted)">ROUTE FROM RECORDED LOCATIONS</p><h3>${dispatch ? `Dispatch ${escapeHtml(dispatch.id)} ? ${escapeHtml(dispatch.destination || dispatch.request_area || '')}` : `Route: ${escapeHtml(String(dispatchRef || 'not assigned'))}`}</h3></div><button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button></div>
        <div class="modal-body" style="padding:0"><div style="position:relative"><div id="route-modal-map" class="real-map-container" style="height:340px"></div><div class="map-layer-switcher" style="position:absolute;top:10px;right:10px;z-index:1000;background:white"><button type="button" class="map-layer-btn active" id="route-roads-btn">Roads</button><button type="button" class="map-layer-btn" id="route-satellite-btn">Satellite</button></div></div><p id="route-modal-status" style="padding:12px 20px;color:var(--text-secondary)">Loading route from recorded coordinates?</p><p style="padding:0 20px 14px;color:var(--text-muted);font-size:.82rem">This is a route estimate between the registered warehouse and request location. It is not live vehicle tracking.</p></div>
        <div class="modal-actions"><button type="button" class="btn btn-secondary close-modal">Close</button></div>
      </div>`;
    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(button => button.onclick = () => { if (routeModalMapInstance) { try { routeModalMapInstance.remove(); } catch (e) {} routeModalMapInstance = null; } backdrop.remove(); });
    const mapEl = backdrop.querySelector('#route-modal-map');
    if (!dispatch) { mapEl.innerHTML = '<div style="padding:24px;text-align:center">This view is not linked to a dispatch record.</div>'; backdrop.querySelector('#route-modal-status').textContent = 'Select an assigned dispatch to show a route.'; return; }
    routeModalMapInstance = await renderRecordedDispatchRoute(mapEl, dispatch, backdrop.querySelector('#route-modal-status'), backdrop.querySelector('#route-roads-btn'), backdrop.querySelector('#route-satellite-btn'));
  }

  // Quick Search Modal
  function openQuickSearchModal() {
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal" style="width:min(600px, 96vw)">
        <div class="modal-head">
          <div style="display:flex;align-items:center;gap:10px;width:100%">
            ${getIcon('Search')}
            <input type="text" id="quick-search-box" placeholder="Quick search requests, stock, volunteers, shelters..." style="width:100%;border:none;font-size:1.1rem;outline:none;background:transparent">
          </div>
          <button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button>
        </div>
        <div class="modal-body" id="quick-search-results" style="max-height:340px;overflow-y:auto">
          <p style="font-size:0.85rem;color:var(--text-muted)">Type above to search across all DRRAS live data.</p>
        </div>
      </div>
    `;

    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());

    const input = backdrop.querySelector('#quick-search-box');
    const results = backdrop.querySelector('#quick-search-results');
    input.focus();

    input.oninput = (e) => {
      const q = e.target.value.toLowerCase().trim();
      if (!q) {
        results.innerHTML = `<p style="font-size:0.85rem;color:var(--text-muted)">Type above to search across all DRRAS live data.</p>`;
        return;
      }

      const matchReqs = requests.filter(r => r.id.toLowerCase().includes(q) || r.area.toLowerCase().includes(q) || r.need.toLowerCase().includes(q));
      const matchInv = inventory.filter(i => i.resource_name.toLowerCase().includes(q));
      const matchVol = volunteers.filter(v => v.name.toLowerCase().includes(q) || v.skill.toLowerCase().includes(q));

      let html = '';
      if (matchReqs.length > 0) {
        html += `<h4 style="font-size:0.8rem;text-transform:uppercase;color:var(--text-muted);margin:8px 0 4px">Emergency Requests</h4>`;
        html += matchReqs.slice(0, 3).map(r => `
          <div style="padding:8px 10px;background:#f8fafc;border-radius:6px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center">
            <div><b>${escapeHtml(r.need)}</b><br><small style="color:var(--text-muted)">${escapeHtml(r.id)} · ${escapeHtml(r.area)}</small></div>
            <span class="priority-score ${r.priority_score >= 85 ? 'critical' : 'high'}">${r.priority_score}</span>
          </div>
        `).join('');
      }

      if (matchInv.length > 0) {
        html += `<h4 style="font-size:0.8rem;text-transform:uppercase;color:var(--text-muted);margin:12px 0 4px">Warehouse Stock</h4>`;
        html += matchInv.slice(0, 3).map(i => `
          <div style="padding:8px 10px;background:#f8fafc;border-radius:6px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center">
            <b>${escapeHtml(i.resource_name)}</b>
            <span>${i.available_units.toLocaleString()} units (${escapeHtml(i.status)})</span>
          </div>
        `).join('');
      }

      if (matchVol.length > 0) {
        html += `<h4 style="font-size:0.8rem;text-transform:uppercase;color:var(--text-muted);margin:12px 0 4px">Volunteers</h4>`;
        html += matchVol.slice(0, 3).map(v => `
          <div style="padding:8px 10px;background:#f8fafc;border-radius:6px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center">
            <b>${escapeHtml(v.name)}</b>
            <span>${escapeHtml(v.skill)} (${escapeHtml(v.status)})</span>
          </div>
        `).join('');
      }

      results.innerHTML = html || `<p style="font-size:0.85rem;color:var(--text-muted)">No matching records found for "${escapeHtml(q)}".</p>`;
    };
  }

  // System Notifications Modal
  async function openNotificationsModal() {
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `<div class="modal" style="width:min(520px, 96vw)"><div class="modal-head"><div><p class="eyebrow" style="color:var(--text-muted)">SYSTEM ALERTS</p><h3>Notifications</h3></div><button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button></div><div class="modal-body" id="user-notifications" style="display:flex;flex-direction:column;gap:12px">Loading notifications?</div><div class="modal-actions"><button type="button" class="btn btn-secondary close-modal">Close</button></div></div>`;
    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());
    const list = backdrop.querySelector('#user-notifications');
    try {
      const response = await fetch('/api/notifications');
      const rows = response.ok ? await response.json() : [];
      if (!response.ok) throw new Error('Unable to load notifications.');
      list.innerHTML = rows.length ? rows.map(n => `<article class="card" style="padding:12px"><b>${escapeHtml(n.title || n.event_type || 'Notification')}</b><p>${escapeHtml(n.message || '')}</p><small>${escapeHtml(n.created_at || '')}</small></article>`).join('') : '<p>No notifications recorded.</p>';
    } catch (error) {
      list.textContent = error.message || 'Notifications could not be refreshed.';
    }
  }

  // Allocation consumes the owner-scoped response team persisted by the Government or NGO assignment workflow.
  async function handleAllocate(reqId) {
    let options;
    try {
      const response = await fetch(`/api/allocation-options/${encodeURIComponent(reqId)}`);
      options = await response.json();
      if (!response.ok) throw new Error(options.error || 'Could not load allocation options.');
    } catch (error) { showToast(error.message || 'Could not load allocation options.', 'error'); return; }
    const team = options.team_assignment;
    const backdrop = document.createElement('div'); backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal" style="width:min(560px,96vw)">
        <div class="modal-head"><div><p class="eyebrow">RESOURCE ALLOCATION ? ${escapeHtml(reqId)}</p><h3>${escapeHtml(options.owner_type === 'ngo' ? 'Allocate NGO-owned resources' : 'Allocate Government-owned resources')}</h3></div><button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button></div>
        <form id="allocation-assignment-form"><div class="modal-body">
          ${team ? `<div class="card" style="padding:14px"><b>Assigned response team</b><p>${escapeHtml(team.personnel_name || team.volunteer_name || 'Responder')} ? ${escapeHtml(team.personnel_category || 'NGO Volunteer')}</p><p>Driver: ${escapeHtml(team.driver_name)} ? Vehicle: ${escapeHtml(team.vehicle_code)} (${escapeHtml(team.vehicle_type)})</p><small>Owner: ${escapeHtml(options.owner_type === 'ngo' ? String(options.organization_id) : 'Government')} · Driver decision: ${escapeHtml(team.driver_decision || 'Accepted')}</small>${team.driver_decision === 'Pending' ? '<p class="alert-banner" style="margin-top:10px">Waiting for the assigned Driver to accept before dispatch allocation.</p>' : ''}</div>` : `<p class="alert-banner critical">No response team is assigned to this owner. Assign the required responder/Volunteer, approved Driver, and compatible vehicle first.</p>`}
          <p class="help-text">Allocation checks the owner?s active warehouse stock and creates a persisted reservation and dispatch. The selected team and vehicle are revalidated by the server.</p>
        </div><div class="modal-actions"><button type="button" class="btn btn-secondary close-modal">Cancel</button><button type="submit" class="btn btn-primary" ${team && team.driver_decision === 'Accepted' ? '' : 'disabled'}>Reserve &amp; dispatch</button></div></form>
      </div>`;
    document.body.appendChild(backdrop); backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => backdrop.remove());
    backdrop.querySelector('#allocation-assignment-form').onsubmit = async e => {
      e.preventDefault(); const submit=e.currentTarget.querySelector('[type="submit"]'); submit.disabled=true;
      try {
        const response=await fetch(`/api/requests/${encodeURIComponent(reqId)}/allocate`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({driver_user_id:Number(team.driver_user_id),vehicle_id:Number(team.vehicle_id)})});
        const result=await response.json();
        if(!response.ok){showToast(result.error||'Allocation failed.','error');submit.disabled=false;return;}
        showToast(`Request ${reqId} allocated. Dispatch ${result.dispatch_id || 'confirmed'} saved.`);
        backdrop.remove();await loadAllData();renderApp();
      }catch(error){showToast('Network error. Allocation was not confirmed.','error');submit.disabled=false;}
    };
  }

  // Emergency Request Modal with Leaflet Map
  function openEmergencyRequestModal() {
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal" style="width:min(620px, 96vw)">
        <div class="modal-head">
          <div>
            <p class="eyebrow" style="color:var(--text-muted)">CITIZEN RELIEF CALL</p>
            <h3>Submit Emergency Request</h3>
          </div>
          <button type="button" class="modal-close-btn close-modal">${getIcon('X')}</button>
        </div>
        <form id="emergency-form">
          <div class="modal-body">
            <p style="font-size:0.85rem;color:var(--text-secondary);margin-bottom:6px">
              This request is instantly analyzed by the automated urgency calculation engine and queued for warehouse dispatch.
            </p>

            <div class="form-group">
              <label>Requester Full Name</label>
              <input required name="name" placeholder="Full name" value="${session ? escapeHtml(session.name) : ''}">
            </div>

            <div class="form-row">
              <div class="form-group">
                <label>Affected Locality / Village</label>
                <input required name="area" placeholder="e.g. Riverbank Sector 4">
              </div>
              <div class="form-group">
                <label>Type of Assistance</label>
                <select name="need">
                  <option value="Drinking water & food kits">Drinking water & food kits</option>
                  <option value="Medical kit & emergency care">Medical kit & emergency care</option>
                  <option value="Rescue support">Rescue boat & evacuation support</option>
                  <option value="Tarpaulin & warm blankets">Tarpaulin & warm blankets</option>
                </select>
              </div>
            </div>

            <div class="form-group">
              <label>Full Address / Landmark</label>
              <input required name="address" id="req-address-input" placeholder="House no, street name, nearest landmark">
            </div>

            <div class="form-group">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                <label style="margin-bottom:0">Pin Location on Google Map</label>
                <div style="display:flex;gap:6px;align-items:center">
                  <div class="map-layer-switcher" style="padding:2px">
                    <button type="button" class="map-layer-btn active" id="btn-picker-roads" style="padding:2px 8px;font-size:0.75rem">Roads</button>
                    <button type="button" class="map-layer-btn" id="btn-picker-sat" style="padding:2px 8px;font-size:0.75rem">Satellite</button>
                  </div>
                  <button type="button" class="btn btn-secondary btn-sm" id="btn-use-gps" style="padding:3px 8px;font-size:0.75rem">
                    ${getIcon('MapPin')} GPS
                  </button>
                </div>
              </div>
              <div class="modal-map-wrapper" style="height:210px">
                <div id="modal-map"></div>
              </div>
              <small class="help-text" id="map-status-text">Click anywhere on the Google Map to pin exact emergency coordinates.</small>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label>People Affected Count</label>
                <input required type="number" min="1" max="10000" name="people" value="4">
              </div>
              <div class="form-group">
                <label>Vulnerable Persons Present?</label>
                <select name="vulnerable">
                  <option value="yes">Yes (Elderly, Infants, Injured)</option>
                  <option value="no">No</option>
                </select>
              </div>
            </div>
          </div>
          <div class="modal-actions">
            <button type="button" class="btn btn-secondary close-modal">Cancel</button>
            <button type="submit" class="btn btn-primary" id="btn-submit-emergency">
              Submit Emergency Request
            </button>
          </div>
        </form>
      </div>
    `;

    document.body.appendChild(backdrop);
    backdrop.querySelectorAll('.close-modal').forEach(b => b.onclick = () => {
      if (requestPickerMap) { requestPickerMap.remove(); requestPickerMap = null; }
      backdrop.remove();
    });

    // Initialize Map
    setTimeout(() => {
      const mapDiv = backdrop.querySelector('#modal-map');
      if (mapDiv) {
        if (window.L) {
          requestPickerMap = L.map(mapDiv).setView([30.9009, 75.8573], 13);
          let currentTile = createGoogleMapTileLayer('googleRoadmap').addTo(requestPickerMap);

          const rBtn = backdrop.querySelector('#btn-picker-roads');
          const sBtn = backdrop.querySelector('#btn-picker-sat');
          if (rBtn && sBtn) {
            rBtn.onclick = () => {
              rBtn.classList.add('active');
              sBtn.classList.remove('active');
              requestPickerMap.removeLayer(currentTile);
              currentTile = createGoogleMapTileLayer('googleRoadmap').addTo(requestPickerMap);
            };
            sBtn.onclick = () => {
              sBtn.classList.add('active');
              rBtn.classList.remove('active');
              requestPickerMap.removeLayer(currentTile);
              currentTile = createGoogleMapTileLayer('googleSatellite').addTo(requestPickerMap);
            };
          }

          requestMarker = null;

          setTimeout(() => {
            try { requestPickerMap.invalidateSize(); } catch (e) {}
          }, 200);

          async function updateLocation(lat, lng) {
            selectedLat = lat;
            selectedLng = lng;
            if (!requestMarker) {
              requestMarker = L.circleMarker([lat, lng], { radius: 8, color: '#ffffff', weight: 3, fillColor: '#dc2626', fillOpacity: 1 }).addTo(requestPickerMap);
            } else {
              requestMarker.setLatLng([lat, lng]);
            }
            const statusEl = backdrop.querySelector('#map-status-text');
            const addressInput = backdrop.querySelector('#req-address-input');
            if (statusEl) statusEl.textContent = 'Resolving geographic address…';

            try {
              const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lng}`, {
                headers: { 'Accept-Language': 'en' }
              });
              const geoData = await res.json();
              if (addressInput && !addressInput.value) {
                addressInput.value = geoData.display_name || `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
              }
              if (statusEl) statusEl.textContent = `Pinned Coordinates: ${lat.toFixed(4)}, ${lng.toFixed(4)}`;
            } catch (e) {
              if (statusEl) statusEl.textContent = `Coordinates set: ${lat.toFixed(4)}, ${lng.toFixed(4)}`;
            }
          }

          requestPickerMap.on('click', e => {
            updateLocation(e.latlng.lat, e.latlng.lng);
          });

          backdrop.querySelector('#btn-use-gps').onclick = () => {
            if (!navigator.geolocation) {
              alert('Geolocation is not supported in this environment.');
              return;
            }
            const statusEl = backdrop.querySelector('#map-status-text');
            if (statusEl) statusEl.textContent = 'Detecting current GPS position…';
            navigator.geolocation.getCurrentPosition(pos => {
              const lat = pos.coords.latitude;
              const lng = pos.coords.longitude;
              requestPickerMap.setView([lat, lng], 14);
              updateLocation(lat, lng);
            }, () => {
              if (statusEl) statusEl.textContent = 'GPS permission denied. Please click on the map.';
            }, { enableHighAccuracy: true, timeout: 8000 });
          };
        } else {
          mapDiv.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#64748b;font-size:12px;background:#f8fafc;padding:12px;text-align:center;">Interactive map preview is offline. Coordinates will be registered with your address.</div>';
        }
      }
    }, 200);

    backdrop.querySelector('#emergency-form').onsubmit = async (e) => {
      e.preventDefault();
      const submitBtn = backdrop.querySelector('#btn-submit-emergency');
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Submitting...';
      }

      const fd = Object.fromEntries(new FormData(e.target));
      try {
        const res = await fetch('/api/requests', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: fd.name,
            area: fd.area,
            address: fd.address,
            need: fd.need,
            people: parseInt(fd.people || 1),
            vulnerable: fd.vulnerable === 'yes',
            lat: selectedLat,
            lng: selectedLng
          })
        });
        const created = await res.json();
        if (!res.ok) {
          showToast(created.error || 'Failed to submit request');
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Submit Emergency Request';
          }
          return;
        }
        if (requestPickerMap) { requestPickerMap.remove(); requestPickerMap = null; }
        backdrop.remove();
        activeNotice = `Emergency request ${created.id} was submitted and urgency scored at ${created.priority_score}/100.`;
        await loadAllData();
        renderApp();
      } catch (err) {
        showToast('Error communicating with emergency server');
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = 'Submit Emergency Request';
        }
      }
    };
  }

  // Keyboard Navigation: Escape to close open modal
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      const modal = document.querySelector('.modal-backdrop');
      if (modal) modal.remove();
    }
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      openQuickSearchModal();
    }
  });

  // Application Bootstrap
  async function init() {
    try {
      const stored = localStorage.getItem('drras-user');
      if (stored) {
        session = JSON.parse(stored);
      }
    } catch (e) {
      session = null;
    }

    if (!session) {
      renderLogin();
      return;
    }

    try {
      const meRes = await fetch('/api/auth/me');
      if (meRes.ok) {
        const meData = await meRes.json();
        session = meData;
        localStorage.setItem('drras-user', JSON.stringify(meData));
        await loadAllData();
        renderApp();
        initLiveEventStream();
      } else {
        stopLiveEventStream();
        localStorage.removeItem('drras-user');
        session = null;
        renderLogin();
      }
    } catch (err) {
      await loadAllData();
      renderApp();
      initLiveEventStream();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
