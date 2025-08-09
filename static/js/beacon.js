;(async () => {
  // Collect browser-only details (best-effort; all optional)
  const nav = navigator || {}
  const scr = screen || {}
  const perf =
    performance && performance.getEntriesByType
      ? performance.getEntriesByType('navigation')[0]
      : null

  const payload = {
    t: new Date().toISOString(),
    href: location.href,
    referrer: document.referrer || null,

    // Locale & time
    lang: nav.language || null,
    languages: nav.languages || null,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || null,

    // Screen & device
    screen: {
      w: scr.width,
      h: scr.height,
      availW: scr.availWidth,
      availH: scr.availHeight,
      dpr: window.devicePixelRatio,
      colorDepth: scr.colorDepth
    },
    hardwareConcurrency: nav.hardwareConcurrency || null,
    deviceMemory: nav.deviceMemory || null,

    // UA (both classic and UA-CH when available)
    userAgent: nav.userAgent || null,
    uaData: nav.userAgentData
      ? {
          mobile: nav.userAgentData.mobile,
          platform: nav.userAgentData.platform,
          brands: nav.userAgentData.brands
        }
      : null,

    // Network info (if supported)
    connection: nav.connection
      ? {
          downlink: nav.connection.downlink,
          rtt: nav.connection.rtt,
          effectiveType: nav.connection.effectiveType,
          saveData: nav.connection.saveData
        }
      : null,

    // Perf timing (if supported)
    navigation: perf
      ? {
          type: perf.type,
          startTime: perf.startTime,
          domContentLoaded: perf.domContentLoadedEventEnd,
          loadEventEnd: perf.loadEventEnd
        }
      : null,

    // Document visibility (handy if you load this hidden)
    visibilityState: document.visibilityState || null,

    // Permissions (sample: notifications)
    permissions: null, // filled below
    battery: null // filled below
  }

  try {
    if (navigator.permissions && navigator.permissions.query) {
      const notif = await navigator.permissions.query({ name: 'notifications' })
      payload.permissions = { notifications: notif.state }
    }
  } catch (_) {}

  try {
    if (navigator.getBattery) {
      const b = await navigator.getBattery()
      payload.battery = { level: b.level, charging: b.charging }
    }
  } catch (_) {}

  // Send (keepalive so it still posts on unload)
  const ts = window.RUN_TS || ''
  try {
    await fetch(`/beacon?ts=${encodeURIComponent(ts)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      keepalive: true,
      credentials: 'same-origin'
    })
  } catch (_) {
    // intentionally swallow
  }
})()
