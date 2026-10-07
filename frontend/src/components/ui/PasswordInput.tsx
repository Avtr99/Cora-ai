/**
 * PasswordInput — password field with a show/hide eye toggle.
 * Shared by the login/claim forms and the account dialog.
 */

import { useState, type InputHTMLAttributes } from "react";
import { Eye, EyeOff } from "lucide-react";

type PasswordInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type">;

const PasswordInput = ({ className = "", ...props }: PasswordInputProps): JSX.Element => {
  const [visible, setVisible] = useState(false);

  return (
    <div className="relative">
      <input
        {...props}
        type={visible ? "text" : "password"}
        className={`${className} pr-11`}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? "Hide password" : "Show password"}
        aria-pressed={visible}
        className="absolute right-3 top-1/2 -translate-y-1/2 rounded-sm text-text-muted hover:text-text-primary transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
      >
        {visible ? (
          <EyeOff className="h-4 w-4" strokeWidth={1.75} />
        ) : (
          <Eye className="h-4 w-4" strokeWidth={1.75} />
        )}
      </button>
    </div>
  );
};

export default PasswordInput;
