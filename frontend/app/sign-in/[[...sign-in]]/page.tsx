import { SignIn } from "@clerk/nextjs";

import { AuthFrame } from "@/components/auth-frame";

export default function SignInPage() {
  return (
    <AuthFrame>
      <SignIn />
    </AuthFrame>
  );
}
