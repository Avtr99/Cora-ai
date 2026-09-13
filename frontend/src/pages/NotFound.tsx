import { useLocation } from "react-router-dom";
import { useEffect } from "react";

const NotFound = () => {
  const location = useLocation();

  useEffect(() => {
    console.error(
      "404 Error: User attempted to access non-existent route:",
      location.pathname
    );
  }, [location.pathname]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-page">
      <div className="text-center">
        <h1 className="text-4xl 3xl:text-5xl 4xl:text-6xl font-bold mb-4">404</h1>
        <p className="text-xl 3xl:text-2xl 4xl:text-3xl text-text-muted mb-4">Oops! Page not found</p>
        <a href="/" className="text-brand-500 hover:text-brand-700 underline text-base 3xl:text-lg 4xl:text-xl">
          Return to Home
        </a>
      </div>
    </div>
  );
};

export default NotFound;
