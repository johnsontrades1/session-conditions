# Setup — machine sleep (run these yourself, needs your password)

**Why:** the pipeline was silently broken for two days. The likeliest cause
is the Mac Mini going to sleep before the 7:40 AM CT LaunchAgent fire —
`launchd` does not wake a sleeping Mac on its own for a `StartCalendarInterval`
job; the machine has to already be awake.

Current state (checked 2026-09-18): `pmset -g` shows `SleepDisabled: 0` and
sleep is only being prevented right now by transient app assertions
(Claude/caffeinate/etc. currently running) — nothing durable is stopping the
machine from sleeping overnight once those processes exit. This needs a real
fix, not an incidental one.

## Option A — disable sleep entirely (recommended for this machine)

```bash
sudo pmset -a sleep 0 disablesleep 1
```

Keeps the Mac Mini always on. **Recommended** because this machine already
runs multiple always-on LaunchAgents (the Kalshi scalper bot, the Polymarket
proxy, this pipeline) — it's functioning as a dedicated automation box, not
a machine you're trying to conserve battery/power on. Simplest fix, zero
dependency on wake-timer reliability.

## Option B — scheduled wake, allow sleep otherwise

```bash
sudo pmset repeat wakeorpoweron MTWRF 07:30:00
```

Wakes the machine at 7:30 AM CT on weekdays (10-minute buffer before the
7:40 fire), but lets it sleep the rest of the time — better if you care about
power draw or want the machine to sleep overnight for some other reason.
Tradeoff: `pmset repeat wakeorpoweron` is known to be occasionally unreliable
(some Mac models/macOS versions miss scheduled wakes, especially after a
recent full shutdown vs. sleep) — worth checking `pmset -g sched` the next
morning after setting it to confirm the wake actually happened.

## Which to pick

Given this Mac Mini's existing role (always-on trading bot host), **Option A**
is the straightforward choice. Only reach for Option B if you specifically
want the machine to sleep when idle and are fine occasionally verifying the
wake fired.

## After running either

Verify the setting stuck:

```bash
pmset -g
```

Look for `SleepDisabled 1` (Option A) or check `pmset -g sched` (Option B)
for the scheduled wake entry.
