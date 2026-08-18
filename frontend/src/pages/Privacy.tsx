// Public, ungated page: a logged-out visitor (and search engines) must be able
// to read it, so it's routed outside RequireAuth/PublicOnly in App.tsx.
//
// The cookie disclosure lives here as the "Cookies" section rather than in a
// separate consent banner: the only cookie the app sets is the strictly-
// necessary httpOnly `refresh_token`, which is exempt from consent under UK
// PECR — it must be described, not opted into. If a non-essential cookie
// (analytics, etc.) is ever added, this stops being sufficient and a real
// consent mechanism is required.
//
// Both of these were placeholders once and are now confirmed: CONTACT_EMAIL is a
// real monitored inbox, and LAST_UPDATED is this version's effective date — bump
// it only when the text below actually changes, not on unrelated edits.
const CONTACT_EMAIL = 'kayaansomchand@hotmail.co.uk'
const LAST_UPDATED = '16 July 2026'

export default function Privacy() {
  return (
    // .prose is the same reading treatment the MDX learn pages get: sans body at
    // a 68ch measure. This is the longest continuous text in the app and the one
    // most punished by a full-width mono column.
    <div className="container-prose prose">
      <h1>Privacy Policy</h1>
      <p className="prose__meta">Last updated: {LAST_UPDATED}</p>

      <p>
        This policy explains what personal data NC++ (&ldquo;we&rdquo;,
        &ldquo;us&rdquo;) collects when you use{' '}
        <a href="https://www.ncplusplus.co.uk">www.ncplusplus.co.uk</a>, why we
        collect it, and the rights you have over it. We are the data controller
        for that data. It is written to align with the UK GDPR and the Data
        Protection Act 2018.
      </p>

      <h2>Who we are</h2>
      <p>
        NC++ is a small educational project that lets you create an account and
        run neural-network training exercises. If you have any question about
        this policy or your data, contact us at{' '}
        <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
      </p>

      <h2>What we collect and why</h2>
      <ul>
        <li>
          <strong>Username</strong> — a public identifier you choose. Used to
          identify your account.
        </li>
        <li>
          <strong>Email address</strong> — used to verify your account, let you
          reset your password, and send you essential account and security
          notices. We do not send marketing emails.
        </li>
        <li>
          <strong>Password</strong> — stored only as a salted{' '}
          <em>bcrypt</em> hash. We never store, log, or have access to your
          plain-text password.
        </li>
        <li>
          <strong>Account timestamps</strong> — when your account was created
          and last used, so the service works and can be maintained.
        </li>
        <li>
          <strong>IP address</strong> — processed when you make requests so we
          can apply rate limits and protect the service from abuse. Because we
          offer limited, free cloud-compute resources for training exercises,
          this is how we stop a small number of users (or automated scripts)
          from exhausting them for everyone. We do not use it to build a profile
          of you.
        </li>
        <li>
          <strong>Training data you submit</strong> — the model configuration
          you choose and the resulting training reports, so we can run your jobs
          and show you the results.
        </li>
      </ul>

      <h2>Lawful bases</h2>
      <p>We rely on two lawful bases under the UK GDPR:</p>
      <ul>
        <li>
          <strong>Performance of a contract</strong> — to create and run your
          account and provide the exercises you ask for.
        </li>
        <li>
          <strong>Legitimate interests</strong> — to keep the service secure,
          available, and free from abuse (for example, applying rate limits and
          detecting misuse of compute resources).
        </li>
      </ul>

      <h2>Cookies</h2>
      <p>
        We use a single, strictly-necessary cookie called{' '}
        <code>refresh_token</code>. It keeps you signed in securely between
        visits. It is an <em>httpOnly</em> cookie (JavaScript cannot read it),
        marked <em>Secure</em> and <em>SameSite=Strict</em>, and it is scoped so
        that it is only ever sent to our authentication endpoint.
      </p>
      <p>
        Because this cookie is essential to sign-in and is set only after you
        choose to log in, it is exempt from consent requirements under the UK
        Privacy and Electronic Communications Regulations (PECR), so we do not
        show a cookie banner. We use <strong>no</strong> analytics, advertising,
        or tracking cookies, and no third-party tracking scripts. If that ever
        changes, we will update this policy and ask for your consent first.
      </p>

      <h2>Who we share it with</h2>
      <p>
        We do not sell your data or share it for advertising. We use a small
        number of service providers who process data on our behalf under
        contract:
      </p>
      <ul>
        <li>
          <strong>Amazon Web Services</strong> — hosting and database, in the UK
          (London) region.
        </li>
        <li>
          <strong>Resend</strong> — delivery of verification, password-reset,
          and security emails.
        </li>
      </ul>
      <p>
        Some providers may process data outside the UK; where they do, that
        processing is covered by appropriate safeguards such as the UK
        International Data Transfer Agreement or equivalent.
      </p>

      <h2>How long we keep it</h2>
      <p>
        We keep your account data for as long as your account exists. Short-lived
        records such as email-verification and password-reset tokens expire
        automatically within hours. If you delete your account, we delete your
        account and its associated data.
      </p>

      <h2>Your rights</h2>
      <p>
        Under the UK GDPR you have the right to access, correct, or delete your
        data, to object to or restrict certain processing, and to data
        portability. In the app you can:
      </p>
      <ul>
        <li>update your email address and password from your account page; and</li>
        <li>
          delete your account, which erases your data, from your account page.
        </li>
      </ul>
      <p>
        For any other request, contact us at{' '}
        <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>. You also have the
        right to complain to the UK&rsquo;s supervisory authority, the
        Information Commissioner&rsquo;s Office (ICO), at{' '}
        <a href="https://ico.org.uk">ico.org.uk</a>.
      </p>

      <h2>Changes to this policy</h2>
      <p>
        If we make material changes we will update this page and the &ldquo;last
        updated&rdquo; date above.
      </p>
    </div>
  )
}
