/**
 * TourStep — final onboarding step.
 *
 * Showcases the five main areas of Cora so new users know what they can do.
 * Each card links directly to its route. The primary CTA sends the user to
 * the chat.
 *
 * Laid out compactly so the entire onboarding viewport fits without scrolling.
 */

import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { IconWrapper } from "@/components/icons/IconWrapper";
import { BRAND } from "@/lib/colors";
import ChatIcon from "@/assets/icons/chat.svg?react";
import BookIcon from "@/assets/icons/book.svg?react";
import PricingIcon from "@/assets/icons/pricing.svg?react";
import ExploreIcon from "@/assets/icons/explore.svg?react";
import FileIcon from "@/assets/icons/file.svg?react";

interface TourStepProps {
  onFinish: () => void;
}

interface TourCard {
  to: string;
  icon: React.FC<React.SVGProps<SVGSVGElement>>;
  title: string;
  description: string;
}

const TOUR_CARDS: TourCard[] = [
  {
    to: "/",
    icon: ChatIcon,
    title: "Chat with Cora",
    description: "Ask any VCM question and get grounded answers with citations.",
  },
  {
    to: "/case-studies/",
    icon: BookIcon,
    title: "Case studies",
    description: "Explore real-world carbon credit projects and what made them work.",
  },
  {
    to: "/pricing/",
    icon: PricingIcon,
    title: "Understanding pricing",
    description: "See the factors that drive carbon credit prices in the VCM.",
  },
  {
    to: "/projects/",
    icon: ExploreIcon,
    title: "Explore projects",
    description: "Browse carbon projects on a map and compare them side by side.",
  },
  {
    to: "/documents/",
    icon: FileIcon,
    title: "Document store",
    description: "Browse the source documents Cora uses to answer your questions.",
  },
];

const TourStep = ({ onFinish }: TourStepProps): JSX.Element => {
  return (
    <div>
      <div className="mb-4">
        <h2 className="font-poppins text-lg md:text-xl font-semibold text-text-primary mb-1">
          What you can do with Cora
        </h2>
        <p className="font-inter text-sm text-text-muted">
          You&apos;re all set. Click any card to jump straight in.
        </p>
      </div>

      <motion.div
        className="grid grid-cols-1 sm:grid-cols-3 gap-3 auto-rows-fr mb-6"
        initial="hidden"
        animate="show"
        variants={{
          hidden: { opacity: 1 },
          show: { opacity: 1, transition: { staggerChildren: 0.06 } },
        }}
      >
        {TOUR_CARDS.map(({ to, icon, title, description }) => (
          <motion.div
            key={title}
            className="h-full"
            variants={{ hidden: { opacity: 0, y: 12 }, show: { opacity: 1, y: 0 } }}
            transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
          >
            <Link
              to={to}
              className="flex items-start gap-3 h-full p-3 rounded-xl bg-surface-card border border-border-ui shadow-card-sm transition-all hover:border-brand-300 hover:shadow-card group"
            >
              <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-brand-100 flex-shrink-0">
                <IconWrapper Icon={icon} size={18} color={BRAND.primary700} aria-hidden={true} />
              </div>
              <div className="min-w-0">
                <h3 className="font-poppins text-sm font-semibold text-text-primary group-hover:text-brand-700 transition-colors">
                  {title}
                </h3>
                <p className="mt-1 font-inter text-xs text-text-muted leading-relaxed">
                  {description}
                </p>
              </div>
            </Link>
          </motion.div>
        ))}
      </motion.div>

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onFinish}
          className="px-7 py-2.5 rounded-lg bg-brand-700 text-white font-poppins text-sm font-semibold shadow-card-md transition-colors hover:bg-brand-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-brand-500"
        >
          Start chatting
        </button>
        <Link
          to="/about/"
          className="font-inter text-sm text-text-muted hover:text-text-primary transition-colors"
        >
          Learn more about Cora
        </Link>
      </div>
    </div>
  );
};

export default TourStep;
