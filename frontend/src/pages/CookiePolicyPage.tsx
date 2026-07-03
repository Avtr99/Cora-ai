import React from 'react';
import LegalPageLayout from '@/components/layout/LegalPageLayout';
import LegalSection from '@/components/ui/LegalSection';

/**
 * Cookie Policy for Cora AI — a self-hosted, local-first application.
 *
 * Cora AI uses minimal local storage only. No tracking cookies are set.
 */
const CookiePolicyPage: React.FC = () => {
  return (
    <LegalPageLayout title="Cookie Policy" lastUpdated="July 2026">

      <LegalSection title="Introduction" number={1}>
        <p>
          This Cookie Policy explains how Cora AI uses browser local storage and cookies. Cora AI is
          a self-hosted, local-first application that does not use tracking cookies or third-party
          analytics. The only client-side storage used is essential local storage required for the
          application to function.
        </p>
      </LegalSection>

      <LegalSection title="Local Storage (Not Cookies)" number={2}>
        <p>
          Cora AI uses the browser's <code>localStorage</code> API to store the following essential
          data on the user's device:
        </p>
        <ul>
          <li><strong>Chat sessions:</strong> Conversation history and session state so users can
            revisit previous chats. This data lives in your browser and is never sent to a server
            unless conversation memory is explicitly enabled by the operator.</li>
          <li><strong>Onboarding status:</strong> A flag (<code>cora_onboarding_complete</code>)
            indicating whether the first-run onboarding wizard has been completed, so it is not
            shown again.</li>
          <li><strong>Visit flag:</strong> A flag (<code>cora_has_visited</code>) indicating the
            user has visited before, used to avoid unnecessary redirects on subsequent visits.</li>
        </ul>
        <p>
          Local storage data persists on your device until you clear it via your browser settings.
          It is not transmitted to any server.
        </p>
      </LegalSection>

      <LegalSection title="No Tracking Cookies" number={3}>
        <p>
          Cora AI does not set any tracking cookies, advertising cookies, or analytics cookies. No
          third-party tracking services (e.g. Google Analytics, PostHog, Mixpanel) are included in
          the default deployment. The application does not collect browsing data, session duration,
          or device fingerprints.
        </p>
      </LegalSection>

      <LegalSection title="No Third-Party Cookies" number={4}>
        <p>
          Because Cora AI is self-hosted and local-first, no third-party services are loaded in the
          browser. The application does not embed third-party widgets, social media plugins, or
          advertising scripts that would set cookies.
        </p>
      </LegalSection>

      <LegalSection title="Managing Local Storage" number={5}>
        <p>
          You can clear all Cora AI data from your browser at any time:
        </p>
        <ul>
          <li><strong>Browser settings:</strong> Clear site data for the Cora AI instance URL in
            your browser's privacy/content settings.</li>
          <li><strong>Developer tools:</strong> Open the browser developer tools (F12), go to the
            Application tab, and clear local storage for the site.</li>
          <li><strong>In-app:</strong> Use the chat interface's "delete chat" or "clear history"
            functionality to remove conversation data.</li>
        </ul>
      </LegalSection>

      <LegalSection title="Operator Note" number={6}>
        <p>
          If an operator modifies their Cora AI deployment to include analytics, third-party
          scripts, or additional cookies, they must update this Cookie Policy to reflect those
          additions and obtain appropriate user consent as required by applicable laws (e.g. the
          EU ePrivacy Directive / GDPR Article 5(3)).
        </p>
      </LegalSection>

      <LegalSection title="Changes to This Policy" number={7}>
        <p>
          This Cookie Policy may be updated as the project evolves. Changes will be posted in the
          project repository and the "Last Updated" date will be revised.
        </p>
      </LegalSection>

      <LegalSection title="Contact" number={8}>
        <p>
          If you have questions about this Cookie Policy, please contact the operator of the Cora AI
          instance you are using. For questions about the project itself, refer to the project
          repository or the contact information provided in the README.
        </p>
      </LegalSection>

    </LegalPageLayout>
  );
};

export default CookiePolicyPage;
