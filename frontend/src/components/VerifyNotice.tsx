import { Link } from 'react-router-dom'
import Message from './Message'

// Shown by both /training and /training/:modelId. Every /train endpoint 403s an
// unverified account, so neither page has anything to fetch — this is the whole
// page in that state, and it needs to say what to do next rather than just what
// is missing.

export default function VerifyNotice() {
  return (
    <div className="container-app">
      <div className="page-header">
        <h1>Training</h1>
      </div>
      <Message kind="info">
        <p>Training jobs require a verified email address.</p>
        <p>
          Check your inbox for the verification link, or{' '}
          <Link to="/">resend it from your home page</Link>.
        </p>
      </Message>
    </div>
  )
}
