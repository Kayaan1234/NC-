// Public, ungated page — same routing treatment as Privacy.tsx: a visitor has to
// be able to read what they are agreeing to *before* they have an account, so it
// sits outside RequireAuth/PublicOnly in App.tsx.
//
// The acceptable-use section is the load-bearing part. NC++ hands anyone with a
// verified email a slice of real cloud compute for free, and the only thing
// standing between that and an abusive script is (a) the rate limits and (b) a
// stated rule that says we may cap or cut off usage at our discretion. The
// technical control without the stated rule is the awkward half.
import { Link } from 'react-router-dom'

const CONTACT_EMAIL = 'kayaansomchand@hotmail.co.uk'
const LAST_UPDATED = '5 August 2026'

export default function Terms() {
  return (
    // Same reading treatment as the privacy policy and the MDX learn pages.
    <div className="container-prose prose">
      <h1>Terms of Service</h1>
      <p className="prose__meta">Last updated: {LAST_UPDATED}</p>

      <p>
        These terms govern your use of NC++ at{' '}
        <a href="https://www.ncplusplus.co.uk">www.ncplusplus.co.uk</a> (the
        &ldquo;service&rdquo;). By creating an account you agree to them. If you
        do not agree, please do not use the service. How we handle your personal
        data is described separately in our{' '}
        <Link to="/privacy">Privacy Policy</Link>.
      </p>

      <h2>What NC++ is</h2>
      <p>
        NC++ is a small, free educational project for learning how neural
        networks are built from first principles in C++. It lets you create an
        account, work through exercises, and run training jobs on compute we
        pay for. It is offered as-is, for learning, and is not a commercial
        product or a hosted training platform.
      </p>

      <h2>Your account</h2>
      <ul>
        <li>
          You must provide a working email address and keep your password
          confidential. You are responsible for activity under your account.
        </li>
        <li>
          One account per person. Do not create accounts automatically, in bulk,
          or to work around a limit applied to another account.
        </li>
        <li>
          You must be old enough to consent to an online service in your country
          (13 in the UK). NC++ is not directed at younger children.
        </li>
        <li>
          Tell us at <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a> if
          you believe your account has been accessed by someone else.
        </li>
      </ul>

      <h2>Acceptable use</h2>
      <p>
        The compute behind the training exercises is finite and shared. These
        rules exist so that one user cannot spend it for everybody else. You
        agree <strong>not</strong> to:
      </p>
      <ul>
        <li>
          submit training jobs automatically, in bulk, or at a rate no human
          would produce by using the site normally;
        </li>
        <li>
          use the service for general-purpose computation, cryptocurrency
          mining, or any workload unrelated to the exercises we provide;
        </li>
        <li>
          attempt to bypass rate limits, quotas, queue positions, or the
          one-job-at-a-time restriction &mdash; including by rotating accounts or
          IP addresses;
        </li>
        <li>
          probe, scan, or attempt to gain unauthorised access to the service,
          other users&rsquo; accounts or data, or the infrastructure behind it;
        </li>
        <li>
          disrupt or degrade the service for others, including by flooding our
          email-sending endpoints or using them to send unwanted mail to an
          address you do not control;
        </li>
        <li>
          resell, sublicense, or offer the service (or the compute behind it) to
          third parties; or
        </li>
        <li>use the service unlawfully, or to infringe anyone&rsquo;s rights.</li>
      </ul>
      <p>
        <strong>Usage limits are at our discretion.</strong> We apply rate limits
        and quotas, and we may change them, apply them to individual accounts, or
        queue, refuse, or cancel a job at any time in order to keep the service
        available and affordable. We do not guarantee any particular amount of
        compute, job duration, or throughput.
      </p>

      <h2>Security research</h2>
      <p>
        If you find a security vulnerability, we would rather hear about it than
        not. Report it to{' '}
        <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a> and give us a
        reasonable chance to fix it before disclosing it. Please do not access
        other users&rsquo; data, degrade the service, or run automated scanning
        against it while testing.
      </p>

      <h2>Content and intellectual property</h2>
      <p>
        The exercises, written material, and code that make up NC++ belong to us
        and are provided for your personal, non-commercial learning. Anything you
        submit &mdash; your model configurations and the training runs they
        produce &mdash; remains yours; you grant us only the permission we need to
        store it and run it in order to provide the service.
      </p>

      <h2>Availability</h2>
      <p>
        The service is provided on a best-effort basis with no uptime guarantee.
        We may change, suspend, or discontinue any part of it, including the
        training queue, at any time. We may take it down for maintenance without
        notice.
      </p>

      <h2>Suspension and termination</h2>
      <p>
        We may suspend or terminate an account that breaches these terms
        &mdash; in particular the acceptable-use rules &mdash; or that puts the
        service, its cost, or its other users at risk. Where it is reasonable to
        do so we will tell you why. You can delete your account at any time from
        your account page, which erases your data as described in the{' '}
        <Link to="/privacy">Privacy Policy</Link>.
      </p>

      <h2>No warranty</h2>
      <p>
        The service is provided &ldquo;as is&rdquo; and &ldquo;as
        available&rdquo;, without warranties of any kind, whether express or
        implied, including fitness for a particular purpose. The exercises are
        educational material, not professional advice, and we do not warrant that
        they are error-free or that the service will be uninterrupted.
      </p>

      <h2>Liability</h2>
      <p>
        To the fullest extent permitted by law, we are not liable for any
        indirect or consequential loss, loss of data, or loss of profit arising
        from your use of the service. Nothing in these terms limits liability
        that cannot be limited by law &mdash; including for death or personal
        injury caused by negligence, or for fraud &mdash; and nothing here
        affects the statutory rights you have as a consumer.
      </p>

      <h2>Changes to these terms</h2>
      <p>
        We may update these terms as the service changes. We will update the
        &ldquo;last updated&rdquo; date above, and for material changes we will
        make a reasonable effort to tell you. Continuing to use the service after
        a change means you accept the updated terms.
      </p>

      <h2>Governing law</h2>
      <p>
        These terms are governed by the laws of England and Wales, and the courts
        of England and Wales have jurisdiction over any dispute. If you are a
        consumer resident elsewhere in the UK, you may also bring proceedings in
        your local courts.
      </p>

      <h2>Contact</h2>
      <p>
        Questions about these terms:{' '}
        <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
      </p>
    </div>
  )
}
