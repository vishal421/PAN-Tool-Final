import React, { useEffect, useMemo, useState } from 'react'
import {
  login, signup, verifyEmail, resendVerification,
  forgotPassword, resendPasswordOtp, resetPassword,
  fetchCountries,
} from '../api'
import { trackActivity } from '../tracking'
import CountrySelect from './CountrySelect'
import StateSelect from './StateSelect'
import { IconMail, IconLock, IconEye, IconEyeOff, IconShield, IconCheckCircle } from './Icons'
import { VENDOR_META } from '../vendorMeta'
import '../styles/landing.css'
import '../styles/seo.css'

const RESEND_COOLDOWN_SECONDS = 60

// Password complexity rules (item: Password Complexity). Each rule is
// re-evaluated live as the user types so the requirements checklist below
// the field can show which ones are still outstanding.
export const PASSWORD_RULES = [
  { key: 'length', label: 'At least 8 characters', test: (p) => p.length >= 8 },
  { key: 'upper', label: 'One uppercase letter', test: (p) => /[A-Z]/.test(p) },
  { key: 'lower', label: 'One lowercase letter', test: (p) => /[a-z]/.test(p) },
  { key: 'number', label: 'One number', test: (p) => /[0-9]/.test(p) },
  { key: 'special', label: 'One special character', test: (p) => /[^A-Za-z0-9]/.test(p) },
]
export const isPasswordValid = (p) => PASSWORD_RULES.every((r) => r.test(p))

// Digits only, 7-15 characters - a real minimum/maximum length check for an
// international mobile number (the country/dial code is captured separately).
const isValidPhoneNumber = (v) => /^\d{7,15}$/.test(v.trim())

// Common personal-webmail and disposable-email domains. Checked after the
// user finishes typing their email (on blur) so the warning only appears
// when it's actually relevant, instead of a static caption shown up front.
const PERSONAL_EMAIL_DOMAINS = new Set([
  'gmail.com', 'googlemail.com', 'yahoo.com', 'ymail.com', 'outlook.com',
  'hotmail.com', 'live.com', 'msn.com', 'rediffmail.com', 'aol.com',
  'icloud.com', 'me.com', 'protonmail.com', 'proton.me', 'zoho.com',
])
const DISPOSABLE_EMAIL_DOMAINS = new Set([
  'mailinator.com', 'tempmail.com', 'temp-mail.org', 'guerrillamail.com',
  '10minutemail.com', 'yopmail.com', 'throwawaymail.com', 'trashmail.com',
  'getnada.com', 'dispostable.com', 'fakeinbox.com', 'sharklasers.com',
])
function personalOrDisposableEmailWarning(emailValue) {
  const at = emailValue.lastIndexOf('@')
  if (at === -1) return null
  const domain = emailValue.slice(at + 1).trim().toLowerCase()
  if (!domain) return null
  if (DISPOSABLE_EMAIL_DOMAINS.has(domain)) {
    return 'That looks like a disposable email address. Please use a permanent email address.'
  }
  if (PERSONAL_EMAIL_DOMAINS.has(domain)) {
    return 'That looks like a personal email address. Please sign up with your corporate/work email address.'
  }
  return null
}

export function PasswordRequirements({ password }) {
  return (
    <ul className="password-requirements">
      {PASSWORD_RULES.map((r) => {
        const met = r.test(password)
        return (
          <li key={r.key} className={met ? 'is-met' : ''}>
            <span className="password-requirement-tick">{met ? '✓' : '•'}</span> {r.label}
          </li>
        )
      })}
    </ul>
  )
}

const emptySignup = {
  firstName: '', lastName: '', email: '', password: '', confirmPassword: '',
  mobileNumber: '', mobileCountryCode: '', organizationName: '',
  city: '', state: '', country: '',
}

// Shared "enter the 6-digit code we emailed you" input, used by both the
// email-verification and password-reset-OTP screens. Renders as six boxes
// but behaves as a single string value/onChange, same as before.
function OtpInput({ value, onChange }) {
  const digits = value.padEnd(6, ' ').split('').slice(0, 6)
  const refs = React.useRef([])

  const setDigit = (idx, raw) => {
    const clean = raw.replace(/[^0-9]/g, '').slice(-1)
    const next = value.split('')
    if (clean) {
      next[idx] = clean
      onChange(next.join('').slice(0, 6))
      if (idx < 5) refs.current[idx + 1]?.focus()
    } else {
      next[idx] = ''
      onChange(next.join('').slice(0, 6))
    }
  }

  const handleKeyDown = (idx, e) => {
    if (e.key === 'Backspace' && !digits[idx].trim() && idx > 0) {
      refs.current[idx - 1]?.focus()
    }
  }

  const handlePaste = (e) => {
    const pasted = e.clipboardData.getData('text').replace(/[^0-9]/g, '').slice(0, 6)
    if (!pasted) return
    e.preventDefault()
    onChange(pasted)
    refs.current[Math.min(pasted.length, 5)]?.focus()
  }

  return (
    <div className="auth-otp-row">
      {digits.map((d, i) => (
        <input
          key={i}
          ref={(el) => (refs.current[i] = el)}
          className="auth-otp-box"
          type="text"
          inputMode="numeric"
          maxLength={1}
          autoComplete={i === 0 ? 'one-time-code' : 'off'}
          value={d.trim()}
          onChange={(e) => setDigit(i, e.target.value)}
          onKeyDown={(e) => handleKeyDown(i, e)}
          onPaste={handlePaste}
        />
      ))}
    </div>
  )
}

function ResendCooldownButton({ onResend, label = 'Resend code' }) {
  const [seconds, setSeconds] = useState(0)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (seconds <= 0) return
    const t = setTimeout(() => setSeconds((s) => s - 1), 1000)
    return () => clearTimeout(t)
  }, [seconds])

  const click = async () => {
    if (seconds > 0 || busy) return
    setBusy(true)
    try {
      await onResend()
      setSeconds(RESEND_COOLDOWN_SECONDS)
    } finally {
      setBusy(false)
    }
  }

  return (
    <button type="button" className="link-btn" onClick={click} disabled={seconds > 0 || busy}>
      {seconds > 0 ? `Resend code (${seconds}s)` : busy ? 'Sending…' : label}
    </button>
  )
}

function AuthBrandPanel() {
  const sourceVendors = VENDOR_META.slice(0, 4)
  return (
    <div className="auth-brand-panel">
      <div className="auth-brand-grid" />
      <div className="auth-brand-blob-1" />
      <div className="auth-brand-blob-2" />

      <div className="auth-brand-top">
        <span className="auth-brand-logo">
          <span className="auth-brand-logo-mark">FC</span>
          <span>
            <span className="auth-brand-logo-text" style={{ display: 'block' }}>Firewall Config Converter</span>
            <span className="auth-brand-logo-sub">firewall.migration.engine</span>
          </span>
        </span>
      </div>

      <div className="auth-brand-mid">
        <span className="auth-brand-eyebrow">
          <span className="dot-live" />
          Migration workspace
        </span>
        <h2 className="auth-brand-headline">
          Migrate any firewall to <span style={{ background: 'var(--gradient-primary)', WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent' }}>Palo Alto</span> in hours, not weeks.
        </h2>
        <p className="auth-brand-sub">
          Convert policies, NAT rules, objects and routes across vendors, with validation and export built in.
        </p>

        <div className="auth-brand-flow">
          <div className="auth-brand-flow-label">Supported migration paths</div>
          <div className="auth-brand-flow-chips">
            {sourceVendors.map((v) => (
              <span key={v.key} className="auth-brand-vendor-chip">{v.label}</span>
            ))}
            <span className="auth-brand-flow-arrow">→</span>
            <span className="auth-brand-target-chip">Palo Alto PAN-OS</span>
          </div>
        </div>

        <ul className="auth-brand-features">
          <li><IconCheckCircle width={16} height={16} /><span>Automated policy, object and NAT translation</span></li>
          <li><IconCheckCircle width={16} height={16} /><span>Interface mapping wizard with per-zone review</span></li>
          <li><IconCheckCircle width={16} height={16} /><span>Pre-export validation and configuration summaries</span></li>
        </ul>
      </div>

      <div className="auth-brand-bottom auth-brand-footer">
        <IconShield width={14} height={14} />
        Your uploaded configs stay private to your workspace
      </div>
    </div>
  )
}

export default function AuthScreen({ onAuthed, initialMode, onSwitchMode }) {
  const [mode, setMode] = useState(initialMode === 'signup' ? 'signup' : 'login')
  // login | signup | verify | forgot | reset
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [otp, setOtp] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [signupData, setSignupData] = useState(emptySignup)
  const [dialCodeTouched, setDialCodeTouched] = useState(false)
  const [countries, setCountries] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [infoMessage, setInfoMessage] = useState(null)
  const [emailWarning, setEmailWarning] = useState(null)
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [showNewPassword, setShowNewPassword] = useState(false)

  useEffect(() => {
    if (mode !== 'signup' || countries.length) return
    fetchCountries().then(setCountries).catch(() => setCountries([]))
  }, [mode, countries.length])

  const setSignupField = (field, value) => setSignupData((d) => ({ ...d, [field]: value }))

  const handleSignupEmailChange = (v) => {
    setEmail(v)
    if (emailWarning) setEmailWarning(null) // don't leave a stale warning up while they're still editing
  }
  const handleSignupEmailBlur = () => setEmailWarning(personalOrDisposableEmailWarning(email))

  // Country Code auto-updates from the selected Country, but only until the
  // user manually picks a different one themselves (per the spec: "with
  // manual override allowed").
  const handleCountryChange = (iso2) => {
    setSignupField('country', iso2)
    setSignupField('state', '')
    if (!dialCodeTouched) {
      const match = countries.find((c) => c.iso2 === iso2)
      if (match) setSignupField('mobileCountryCode', match.dial_code)
    }
  }
  const handleDialCodeChange = (dial) => {
    setDialCodeTouched(true)
    setSignupField('mobileCountryCode', dial)
  }

  const signupValid = useMemo(() => {
    const d = signupData
    return d.firstName.trim() && d.lastName.trim() && email.trim() && isPasswordValid(password) &&
      password === d.confirmPassword &&
      d.mobileNumber.trim() && isValidPhoneNumber(d.mobileNumber) && d.mobileCountryCode.trim() && d.organizationName.trim() &&
      d.city.trim() && d.country.trim()
  }, [signupData, email, password])

  const phoneTouched = signupData.mobileNumber.length > 0
  const phoneError = phoneTouched && !isValidPhoneNumber(signupData.mobileNumber)
    ? 'Enter a valid phone number (digits only, 7–15 digits).' : null

  const passwordsMismatch = signupData.confirmPassword.length > 0 && password !== signupData.confirmPassword

  const switchMode = (next) => {
    // On a real login./signup. subdomain deployment, switching between the
    // login and signup forms is a real cross-origin navigation so the
    // browser URL always matches what's on screen - see App.jsx's authUrl().
    // Other transitions (forgot/verify/reset) stay on the same page/host.
    if ((next === 'login' || next === 'signup') && onSwitchMode) {
      onSwitchMode(next)
      return
    }
    setMode(next)
    setError(null)
    setInfoMessage(null)
    setEmailWarning(null)
    setOtp('')
  }

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setInfoMessage(null)
    try {
      if (mode === 'login') {
        const resp = await login(email, password)
        trackActivity('login')
        onAuthed(resp.user)
      } else if (mode === 'signup') {
        const signupEmail = email
        await signup({
          first_name: signupData.firstName.trim(),
          last_name: signupData.lastName.trim(),
          email,
          password,
          mobile_number: signupData.mobileNumber.trim(),
          mobile_country_code: signupData.mobileCountryCode.trim(),
          organization_name: signupData.organizationName.trim(),
          city: signupData.city.trim(),
          state: signupData.state.trim() || undefined,
          country: signupData.country,
        })
        trackActivity('signup_completed')
        setEmail(signupEmail)
        setPassword('')
        setSignupData(emptySignup)
        setMode('verify')
      } else if (mode === 'verify') {
        const resp = await verifyEmail(email, otp)
        setInfoMessage(resp.message)
        setOtp('')
        setTimeout(() => switchMode('login'), 1200)
      } else if (mode === 'forgot') {
        await forgotPassword(email)
        // Deliberately not setting infoMessage here - the 'reset' screen's
        // own hint text already confirms a code was sent, and 'reset'
        // reuses infoMessage/!infoMessage to show its *own* post-submit
        // success state and hide the Update Password button. Carrying the
        // 'forgot' message over would hide that button the moment the
        // reset screen appears, before the user ever gets to use it.
        setMode('reset')
      } else if (mode === 'reset') {
        const resp = await resetPassword(email, otp, newPassword)
        setInfoMessage(resp.message)
        setOtp('')
        setNewPassword('')
        setTimeout(() => switchMode('login'), 1200)
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const isLogin = mode === 'login'

  return (
    <div className={`auth-shell ${isLogin ? 'auth-shell-split' : ''}`}>
      {isLogin && <AuthBrandPanel />}
      <div className={isLogin ? 'auth-form-panel' : ''}>
        {isLogin && (
          <a href="/" className="auth-form-mobile-brand">
            <span className="auth-brand-logo-mark" style={{ height: 32, width: 32, fontSize: 13 }}>FC</span>
            <span style={{ fontWeight: 700, fontSize: 14 }}>Firewall Config Converter</span>
          </a>
        )}
        <div className="card auth-card">
          {!isLogin && (
            <div className="app-title" style={{ justifyContent: 'center', marginBottom: 8 }}>
              <span className="mark">FC</span>
              Firewall Config Converter
            </div>
          )}

          {mode === 'login' && <h2 style={{ textAlign: isLogin ? 'left' : 'center' }}>Welcome back</h2>}
          {mode === 'signup' && <h2 style={{ textAlign: 'center' }}>Create Your Account</h2>}
          {mode === 'verify' && <h2 style={{ textAlign: 'center' }}>Verify Your Email</h2>}
          {mode === 'forgot' && <h2 style={{ textAlign: 'center' }}>Reset Your Password</h2>}
          {mode === 'reset' && <h2 style={{ textAlign: 'center' }}>Choose a New Password</h2>}

          <p className="hint" style={{ textAlign: isLogin ? 'left' : 'center' }}>
            {mode === 'login' && 'Sign in to continue your migration workspace.'}
            {mode === 'signup' && 'Sign up with your corporate email address. Free plan includes up to 10 saved conversion jobs.'}
            {mode === 'verify' && `Enter the 6-digit code we sent to ${email}.`}
            {mode === 'forgot' && "Enter your email and we'll send you a password reset code."}
            {mode === 'reset' && `Enter the code we sent to ${email} and choose a new password.`}
          </p>

          {mode === 'login' && (
            <form onSubmit={submit}>
              {infoMessage && <div className="success-box" style={{ marginBottom: 12 }}>{infoMessage}</div>}
              <label className="auth-label">Email</label>
              <div className="auth-input-group">
                <span className="auth-input-icon"><IconMail width={16} height={16} /></span>
                <input
                  className="grid-input auth-input"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  placeholder="you@company.com"
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <label className="auth-label" style={{ margin: '14px 0 6px' }}>Password</label>
                <button type="button" className="link-btn" style={{ fontSize: 12 }} onClick={() => switchMode('forgot')}>Forgot?</button>
              </div>
              <div className="auth-input-group has-toggle">
                <span className="auth-input-icon"><IconLock width={16} height={16} /></span>
                <input
                  className="grid-input auth-input"
                  type={showPassword ? 'text' : 'password'}
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  placeholder="••••••••••"
                />
                <button type="button" className="auth-input-toggle" onClick={() => setShowPassword((s) => !s)} tabIndex={-1}>
                  {showPassword ? <IconEyeOff width={16} height={16} /> : <IconEye width={16} height={16} />}
                </button>
              </div>

              {error && (
                <div className="error-box">
                  {error}
                  {/* Login blocked pending verification - offer a quick path back in. */}
                  {/^please verify your email/i.test(error) && (
                    <div style={{ marginTop: 8 }}>
                      <button type="button" className="link-btn" onClick={() => switchMode('verify')}>
                        Enter verification code
                      </button>
                    </div>
                  )}
                </div>
              )}

              <button className="btn btn-primary" type="submit" disabled={loading} style={{ width: '100%', marginTop: 16 }}>
                {loading ? 'Please wait…' : 'Sign In'}
              </button>
            </form>
          )}

          {mode === 'signup' && (
            <form onSubmit={submit}>
              {/* Row 1: First Name / Last Name / Email */}
              <div className="field-grid-3">
                <div>
                  <label className="auth-label">First Name *</label>
                  <input className="grid-input auth-input" required value={signupData.firstName}
                    onChange={(e) => setSignupField('firstName', e.target.value)} autoComplete="given-name" />
                </div>
                <div>
                  <label className="auth-label">Last Name *</label>
                  <input className="grid-input auth-input" required value={signupData.lastName}
                    onChange={(e) => setSignupField('lastName', e.target.value)} autoComplete="family-name" />
                </div>
                <div>
                  <label className="auth-label">Corporate Email *</label>
                  <div className="auth-input-group">
                    <span className="auth-input-icon"><IconMail width={16} height={16} /></span>
                    <input className="grid-input auth-input" type="email" required value={email}
                      onChange={(e) => handleSignupEmailChange(e.target.value)} onBlur={handleSignupEmailBlur}
                      autoComplete="email" placeholder="you@company.com" />
                  </div>
                </div>
              </div>
              {emailWarning && (
                <div className="auth-inline-warning" role="alert">
                  {emailWarning}
                </div>
              )}

              {/* Row 2: Mobile Number / Organization */}
              <div className="field-grid-2" style={{ marginTop: 12 }}>
                <div>
                  <label className="auth-label">Phone Number *</label>
                  <div className="field-grid-2" style={{ gridTemplateColumns: '110px 1fr' }}>
                    <CountrySelect
                      countries={countries}
                      mode="dial"
                      value={signupData.mobileCountryCode}
                      onChange={handleDialCodeChange}
                      placeholder="Code"
                    />
                    <input className="grid-input auth-input" type="tel" inputMode="numeric" required
                      value={signupData.mobileNumber}
                      onChange={(e) => setSignupField('mobileNumber', e.target.value.replace(/[^0-9]/g, '').slice(0, 15))}
                      placeholder="e.g. 9876543210" autoComplete="tel-national" />
                  </div>
                  {phoneError && (
                    <div className="hint" style={{ marginTop: 4, marginBottom: 0, color: 'var(--error, #b91c1c)' }}>
                      {phoneError}
                    </div>
                  )}
                </div>
                <div>
                  <label className="auth-label">Organization / Company *</label>
                  <input className="grid-input auth-input" required value={signupData.organizationName}
                    onChange={(e) => setSignupField('organizationName', e.target.value)} autoComplete="organization" />
                </div>
              </div>

              {/* Row 3: Password / Confirm Password */}
              <div className="field-grid-2" style={{ marginTop: 12 }}>
                <div>
                  <label className="auth-label">Password *</label>
                  <div className="auth-input-group has-toggle">
                    <span className="auth-input-icon"><IconLock width={16} height={16} /></span>
                    <input className="grid-input auth-input" type={showPassword ? 'text' : 'password'} required minLength={8} value={password}
                      onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" placeholder="••••••••••" />
                    <button type="button" className="auth-input-toggle" onClick={() => setShowPassword((s) => !s)} tabIndex={-1}>
                      {showPassword ? <IconEyeOff width={16} height={16} /> : <IconEye width={16} height={16} />}
                    </button>
                  </div>
                </div>
                <div>
                  <label className="auth-label">Confirm Password *</label>
                  <div className="auth-input-group has-toggle">
                    <span className="auth-input-icon"><IconLock width={16} height={16} /></span>
                    <input className="grid-input auth-input" type={showConfirmPassword ? 'text' : 'password'} required minLength={8}
                      value={signupData.confirmPassword}
                      onChange={(e) => setSignupField('confirmPassword', e.target.value)} autoComplete="new-password" placeholder="••••••••••" />
                    <button type="button" className="auth-input-toggle" onClick={() => setShowConfirmPassword((s) => !s)} tabIndex={-1}>
                      {showConfirmPassword ? <IconEyeOff width={16} height={16} /> : <IconEye width={16} height={16} />}
                    </button>
                  </div>
                </div>
              </div>
              <PasswordRequirements password={password} />
              {passwordsMismatch && (
                <div className="hint" style={{ marginTop: -4, marginBottom: 4, color: 'var(--danger, #b91c1c)' }}>
                  Passwords do not match.
                </div>
              )}

              {/* Row 4: Country / State / City */}
              <div className="field-grid-3" style={{ marginTop: 12 }}>
                <div>
                  <label className="auth-label">Country *</label>
                  <CountrySelect
                    countries={countries}
                    mode="country"
                    value={signupData.country}
                    onChange={handleCountryChange}
                    placeholder="Select country"
                  />
                </div>
                <div>
                  <label className="auth-label">State / Province</label>
                  <StateSelect
                    countryIso2={signupData.country}
                    value={signupData.state}
                    onChange={(v) => setSignupField('state', v)}
                    placeholder="Select state"
                  />
                </div>
                <div>
                  <label className="auth-label">City *</label>
                  <input className="grid-input auth-input" required value={signupData.city}
                    onChange={(e) => setSignupField('city', e.target.value)} autoComplete="address-level2" />
                </div>
              </div>

              {error && <div className="error-box" style={{ marginTop: 12 }}>{error}</div>}

              <button className="btn btn-primary" type="submit" disabled={loading || !signupValid} style={{ width: '100%', marginTop: 16 }}>
                {loading ? 'Please wait…' : 'Sign Up'}
              </button>
            </form>
          )}

          {mode === 'verify' && (
            <form onSubmit={submit}>
              <label className="auth-label">Verification Code</label>
              <OtpInput value={otp} onChange={setOtp} />

              {error && <div className="error-box" style={{ marginTop: 12 }}>{error}</div>}
              {infoMessage && <div className="success-box" style={{ marginTop: 12 }}>{infoMessage}</div>}

              {!infoMessage && (
                <button className="btn btn-primary" type="submit" disabled={loading || otp.length !== 6} style={{ width: '100%', marginTop: 12 }}>
                  {loading ? 'Please wait…' : 'Verify Email'}
                </button>
              )}

              <div className="auth-switch" style={{ marginTop: 12 }}>
                <ResendCooldownButton onResend={() => resendVerification(email)} />
              </div>
            </form>
          )}

          {mode === 'forgot' && infoMessage == null && (
            <form onSubmit={submit}>
              <label className="auth-label">Email</label>
              <div className="auth-input-group">
                <span className="auth-input-icon"><IconMail width={16} height={16} /></span>
                <input
                  className="grid-input auth-input"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                />
              </div>
              {error && <div className="error-box">{error}</div>}
              <button className="btn btn-primary" type="submit" disabled={loading} style={{ width: '100%', marginTop: 8 }}>
                {loading ? 'Please wait…' : 'Send Reset Code'}
              </button>
            </form>
          )}

          {mode === 'reset' && (
            <form onSubmit={submit}>
              <label className="auth-label">Reset Code</label>
              <OtpInput value={otp} onChange={setOtp} />

              <label className="auth-label" style={{ marginTop: 12 }}>New Password</label>
              <div className="auth-input-group has-toggle">
                <span className="auth-input-icon"><IconLock width={16} height={16} /></span>
                <input
                  className="grid-input auth-input"
                  type={showNewPassword ? 'text' : 'password'}
                  required
                  minLength={8}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  autoComplete="new-password"
                />
                <button type="button" className="auth-input-toggle" onClick={() => setShowNewPassword((s) => !s)} tabIndex={-1}>
                  {showNewPassword ? <IconEyeOff width={16} height={16} /> : <IconEye width={16} height={16} />}
                </button>
              </div>
              <PasswordRequirements password={newPassword} />
              {error && <div className="error-box">{error}</div>}
              {infoMessage && <div className="success-box">{infoMessage}</div>}
              {!infoMessage && (
                <>
                  <button className="btn btn-primary" type="submit" disabled={loading || otp.length !== 6 || !isPasswordValid(newPassword)}
                    style={{ width: '100%', marginTop: 8 }}>
                    {loading ? 'Please wait…' : 'Update Password'}
                  </button>
                  <div className="auth-switch" style={{ marginTop: 12 }}>
                    <ResendCooldownButton onResend={() => resendPasswordOtp(email)} />
                  </div>
                </>
              )}
            </form>
          )}

          {(mode === 'login' || mode === 'signup') && (
            <div className="auth-switch" style={{ textAlign: isLogin ? 'left' : 'center' }}>
              {mode === 'login' ? (
                <>Don't have an account? <button className="link-btn" onClick={() => switchMode('signup')}>Sign up</button></>
              ) : (
                <>Already have an account? <button className="link-btn" onClick={() => switchMode('login')}>Log in</button></>
              )}
            </div>
          )}

          {(mode === 'forgot' || mode === 'verify' || mode === 'reset') && (
            <div className="auth-switch">
              <button className="link-btn" onClick={() => switchMode('login')}>Back to login</button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
