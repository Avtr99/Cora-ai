/**
 * AccountDialog — the signed-in user's own account surface (change password).
 * Separate from SettingsDialog on purpose: Settings is instance-level config,
 * this is personal — the same split as Open WebUI, n8n, and Immich.
 * Rendered only for authenticated users (protection on).
 */

import { useEffect, useState, type FormEvent } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { changeOwnPassword } from "@/services/accountApi";
import { useAuthStore } from "@/store/authStore";
import { MIN_PASSWORD_LENGTH, passwordError } from "@/components/auth/passwordRule";
import PasswordInput from "@/components/ui/PasswordInput";
import {
  Field,
  ErrorBox,
  SavedBanner,
  inputClass,
} from "@/components/settings/settingsPrimitives";

interface AccountDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const AccountDialog = ({ open, onOpenChange }: AccountDialogProps): JSX.Element => {
  const user = useAuthStore((s) => s.user);
  const [pwCurrent, setPwCurrent] = useState("");
  const [pwNew, setPwNew] = useState("");
  const [pwConfirm, setPwConfirm] = useState("");
  const [pwSaving, setPwSaving] = useState(false);
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwSaved, setPwSaved] = useState(false);

  // Reopen with a clean form — a previous success banner or error must not
  // carry into the next visit.
  useEffect(() => {
    if (open) {
      setPwCurrent("");
      setPwNew("");
      setPwConfirm("");
      setPwError(null);
      setPwSaved(false);
    }
  }, [open]);

  const canSubmit = Boolean(pwCurrent && pwNew && pwConfirm);

  const handleChangePassword = async (e: FormEvent): Promise<void> => {
    e.preventDefault();
    if (!canSubmit || pwSaving) return;
    setPwError(null);
    const ruleError = passwordError(pwNew);
    if (ruleError) {
      setPwError(ruleError);
      return;
    }
    if (pwNew !== pwConfirm) {
      setPwError("Passwords do not match.");
      return;
    }
    setPwSaving(true);
    try {
      await changeOwnPassword(pwCurrent, pwNew);
      setPwSaved(true);
    } catch (err) {
      setPwError(err instanceof Error ? err.message : String(err));
    } finally {
      setPwSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md max-h-[90vh] overflow-y-auto rounded-xl border border-border-ui bg-surface-card shadow-modal p-5 3xl:p-6 4xl:p-7 gap-0">
        <DialogHeader className="space-y-0 text-left">
          <DialogTitle className="font-poppins text-heading-2 font-semibold text-text-primary">
            Account
          </DialogTitle>
          <DialogDescription className="sr-only">
            Your Cora account
          </DialogDescription>
        </DialogHeader>

        {/* Identity — who this account is, at a glance */}
        <div className="mt-4 flex items-center gap-3 3xl:gap-4 rounded-xl border border-border-ui bg-surface-subtle px-3.5 3xl:px-4 py-3 3xl:py-3.5">
          <span
            aria-hidden="true"
            className="flex h-10 w-10 3xl:h-11 3xl:w-11 shrink-0 items-center justify-center rounded-full bg-brand-700 font-poppins text-sm 3xl:text-base font-semibold uppercase text-white select-none"
          >
            {user?.username?.slice(0, 2) ?? "?"}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate font-poppins text-body-sm 3xl:text-base font-semibold text-text-primary">
              {user?.username ?? "Account"}
            </p>
            <p className="font-inter text-caption 3xl:text-sm text-text-muted">
              Signed in on this instance
            </p>
          </div>
          <span className="inline-flex shrink-0 items-center rounded-full border border-border-ui bg-surface-card px-2.5 py-1 font-inter text-caption 3xl:text-sm font-medium text-text-secondary">
            Owner
          </span>
        </div>

        {pwSaved ? (
          <div>
            <SavedBanner
              title="Password changed"
              text="Your other sessions were signed out."
            />
            <div className="flex justify-end">
              <button
                type="button"
                onClick={() => onOpenChange(false)}
                className="inline-flex h-9 3xl:h-10 items-center px-4 3xl:px-5 rounded-lg bg-brand-700 text-white font-poppins text-body-sm 3xl:text-base font-semibold transition-colors hover:bg-brand-hover focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2"
              >
                Done
              </button>
            </div>
          </div>
        ) : (
          <form
            onSubmit={(e) => void handleChangePassword(e)}
            className="mt-4 space-y-2.5 3xl:space-y-3 border-t border-border-ui pt-4"
          >
            <p className="font-poppins text-body-sm 3xl:text-base font-medium text-text-primary">
              Change password
            </p>
            <Field label="Current password">
              <PasswordInput
                value={pwCurrent}
                onChange={(e) => setPwCurrent(e.target.value)}
                autoComplete="current-password"
                className={inputClass}
              />
            </Field>
            <Field label="New password" hint={`at least ${MIN_PASSWORD_LENGTH} characters`}>
              <PasswordInput
                value={pwNew}
                onChange={(e) => setPwNew(e.target.value)}
                autoComplete="new-password"
                className={inputClass}
              />
            </Field>
            <Field label="Confirm new password">
              <PasswordInput
                value={pwConfirm}
                onChange={(e) => setPwConfirm(e.target.value)}
                autoComplete="new-password"
                className={inputClass}
              />
            </Field>

            {pwError && <ErrorBox message={pwError} />}

            <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
              <p className="font-inter text-caption 3xl:text-sm text-text-muted">
                Signs out your other sessions.
              </p>
              <div className="flex gap-2 3xl:gap-3">
                <button
                  type="button"
                  onClick={() => onOpenChange(false)}
                  className="inline-flex h-9 3xl:h-10 items-center px-4 3xl:px-5 rounded-lg border border-border-ui text-text-secondary font-poppins text-body-sm 3xl:text-base font-medium transition-colors hover:border-text-muted hover:bg-surface-subtle focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={pwSaving || !canSubmit}
                  className="inline-flex h-9 3xl:h-10 items-center px-4 3xl:px-5 rounded-lg bg-brand-700 text-white font-poppins text-body-sm 3xl:text-base font-semibold shadow-card-md transition-colors hover:bg-brand-hover disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2"
                >
                  {pwSaving ? "Changing..." : "Change password"}
                </button>
              </div>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default AccountDialog;
