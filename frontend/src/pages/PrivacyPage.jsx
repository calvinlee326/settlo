import { Link } from 'react-router-dom';

const CONTACT_EMAIL = 'calvinlee326@gmail.com';

function Section({ title, children }) {
  return (
    <section className="space-y-2">
      <h2 className="text-[17px] font-semibold text-ink">{title}</h2>
      <div className="space-y-2 text-[15px] text-ink-soft">{children}</div>
    </section>
  );
}

export default function PrivacyPage() {
  return (
    <div className="page-enter mx-auto max-w-[640px] px-4 py-12">
      <div className="card space-y-6 p-8">
        <div>
          <h1 className="text-[28px] font-semibold text-ink">Privacy Policy</h1>
          <p className="mt-1 text-[13px] text-muted">Last updated: October 1, 2026</p>
        </div>

        <p className="text-[15px] text-ink-soft">
          Settlo is an app for splitting bills with friends. This page explains
          what we collect, why, and how to have it deleted.
        </p>

        <Section title="What we collect">
          <ul className="list-disc space-y-1 pl-5">
            <li>
              <strong>Phone number</strong>, if you sign in with your phone. We use
              it to sign you in and so friends can add you.
            </li>
            <li>
              <strong>Google account details</strong>, if you sign in with Google:
              your Google account ID, email address and name. We use them to sign
              you in and to set your display name.
            </li>
            <li>
              <strong>Your display name.</strong>
            </li>
            <li>
              <strong>What you enter in Settlo</strong>: groups, expenses, payments,
              friends and invitations.
            </li>
          </ul>
        </Section>

        <Section title="How we use it">
          <p>
            Only to run Settlo: signing you in, working out balances, and showing
            them to the people you share a group or friendship with. We do not sell
            your data, show ads, or track you across other sites.
          </p>
        </Section>

        <Section title="Who can see it">
          <p>
            Members of your groups see your display name and the expenses and
            payments in those groups. Your friends see your display name and phone
            number. Settlo never moves money; payments you record are only notes
            that a payment happened elsewhere.
          </p>
        </Section>

        <Section title="Services we rely on">
          <ul className="list-disc space-y-1 pl-5">
            <li>Twilio, to send sign-in codes by SMS (receives your phone number)</li>
            <li>Google, for Google sign-in</li>
            <li>Railway, which hosts our server and database</li>
            <li>Vercel, which hosts this website</li>
            <li>Google Fonts, which serves the app&apos;s font (receives your IP address)</li>
          </ul>
        </Section>

        <Section title="Cookies">
          <p>
            We use one cookie, only to keep you signed in. There are no advertising
            or analytics cookies.
          </p>
        </Section>

        <Section title="Deleting your data">
          <p>
            Email{' '}
            <a href={`mailto:${CONTACT_EMAIL}`} className="font-medium text-ink underline">
              {CONTACT_EMAIL}
            </a>{' '}
            from the email address or phone number on your account, and we will
            delete your account and personal information.
          </p>
        </Section>

        <Section title="Contact">
          <p>
            Questions about this policy:{' '}
            <a href={`mailto:${CONTACT_EMAIL}`} className="font-medium text-ink underline">
              {CONTACT_EMAIL}
            </a>
          </p>
        </Section>

        <Link to="/login" className="inline-block text-sm text-muted hover:text-ink">
          Back to Settlo
        </Link>
      </div>
    </div>
  );
}
