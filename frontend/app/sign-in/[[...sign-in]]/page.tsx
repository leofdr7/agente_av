import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <main className="shop-grid flex flex-1 items-center justify-center px-4 py-12">
      <SignIn />
    </main>
  );
}
