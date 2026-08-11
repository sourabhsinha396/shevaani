import { config } from "@/lib/config";

/**
 * Legal and contact details used on the contact and policy pages, here rather
 * than inline so replacing them is one edit.
 *
 * Address, phone and email come from env because Razorpay's onboarding wants
 * all three reachable on the site, and a change of number or office should not
 * be a code change. NEXT_PUBLIC_ because these are printed on public pages
 * anyway, so there is nothing to keep out of the bundle.
 */
export const company = {
  legalName: process.env.NEXT_PUBLIC_COMPANY_LEGAL_NAME ?? config.appName,
  brand: config.appName,
  address: process.env.NEXT_PUBLIC_COMPANY_ADDRESS ?? "",
  phone: process.env.NEXT_PUBLIC_COMPANY_PHONE ?? "",
  supportEmail: process.env.NEXT_PUBLIC_COMPANY_EMAIL ?? "",
};
