import { useState, type FormEvent } from "react";
import {
  Database,
  FileText,
  LockKeyhole,
  Mail,
  ShieldCheck,
  Trash2,
  UserRound,
} from "lucide-react";
import { Link } from "react-router-dom";
import { WorkspaceShell } from "@/components/SiteChrome";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { deleteAccount, type User } from "@/lib/api";

export function AccountPage({
  user,
  onSignOut,
  onAccountDeleted,
}: {
  user: User;
  onSignOut: () => void;
  onAccountDeleted: () => void;
}) {
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteStep, setDeleteStep] = useState<1 | 2>(1);
  const [confirmation, setConfirmation] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  function closeDeleteDialog(nextOpen: boolean) {
    if (deleting) return;
    setDeleteOpen(nextOpen);
    if (!nextOpen) {
      setDeleteStep(1);
      setConfirmation("");
      setDeleteError("");
    }
  }

  async function confirmDelete(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (confirmation !== "DELETE") return;
    setDeleting(true);
    setDeleteError("");
    try {
      await deleteAccount();
      onAccountDeleted();
    } catch (error) {
      setDeleteError(
        error instanceof Error
          ? error.message
          : "We couldn't complete account deletion. Some cleanup may have finished; please try again.",
      );
      setDeleting(false);
    }
  }

  return (
    <WorkspaceShell user={user} onSignOut={onSignOut}>
      <div className="account-heading">
        <div>
          <p className="section-kicker">Account & privacy</p>
          <h1 className="page-title mt-3">Your workspace, your data.</h1>
          <p className="page-copy mt-3">
            Review the information connected to your account and understand how
            CareerStack handles it.
          </p>
        </div>
      </div>

      <div className="account-layout mt-8">
        <div className="grid gap-5">
          <section className="account-panel" aria-labelledby="profile-heading">
            <div className="account-panel-heading">
              <div className="account-panel-icon" aria-hidden="true">
                <UserRound className="size-5" />
              </div>
              <div>
                <h2 id="profile-heading" className="text-lg font-semibold tracking-[-0.025em]">
                  Profile details
                </h2>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                  These details identify your private workspace.
                </p>
              </div>
            </div>
            <dl className="account-details mt-6">
              <div>
                <dt>
                  <UserRound className="size-4" aria-hidden="true" /> Name
                </dt>
                <dd>{user.name}</dd>
              </div>
              <div>
                <dt>
                  <Mail className="size-4" aria-hidden="true" /> Email
                </dt>
                <dd className="break-all">{user.email}</dd>
              </div>
            </dl>
          </section>

          <section className="account-panel" aria-labelledby="privacy-heading">
            <div className="account-panel-heading">
              <div className="account-panel-icon" aria-hidden="true">
                <ShieldCheck className="size-5" />
              </div>
              <div>
                <h2 id="privacy-heading" className="text-lg font-semibold tracking-[-0.025em]">
                  Privacy and data
                </h2>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                  A plain-language summary of what the workspace handles.
                </p>
              </div>
            </div>
            <ul className="account-privacy-list mt-6">
              <li>
                <FileText className="size-4 shrink-0" aria-hidden="true" />
                <div>
                  <h3>Analyses you create</h3>
                  <p>Resume content, target role, and location are processed to produce and save your analysis.</p>
                </div>
              </li>
              <li>
                <Database className="size-4 shrink-0" aria-hidden="true" />
                <div>
                  <h3>Saved work and matches</h3>
                  <p>Your account keeps your analyses and the matching-role views built from them available when you return.</p>
                </div>
              </li>
              <li>
                <LockKeyhole className="size-4 shrink-0" aria-hidden="true" />
                <div>
                  <h3>No model training or sale</h3>
                  <p>Your resume is not used to train a model, and CareerStack does not sell personal information.</p>
                </div>
              </li>
            </ul>
            <Link
              to="/privacy"
              className="mt-6 inline-flex text-sm font-semibold text-accent underline underline-offset-4"
            >
              Read the full privacy summary
            </Link>
          </section>
        </div>

        <aside>
          <section className="account-danger-zone" aria-labelledby="delete-heading">
            <div className="account-danger-icon" aria-hidden="true">
              <Trash2 className="size-5" />
            </div>
            <p className="section-kicker mt-6 text-destructive">Destructive action</p>
            <h2 id="delete-heading" className="mt-2 text-xl font-semibold tracking-[-0.03em]">
              Delete this account
            </h2>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              Permanently remove your account and its saved workspace data. This
              cannot be undone.
            </p>
            <Button
              variant="destructive"
              className="mt-6 w-full"
              onClick={() => setDeleteOpen(true)}
            >
              <Trash2 aria-hidden="true" />
              Delete account
            </Button>
          </section>
        </aside>
      </div>

      <Dialog
        open={deleteOpen}
        onOpenChange={(nextOpen) => closeDeleteDialog(nextOpen)}
      >
        <DialogContent>
          <DialogHeader>
            <p className="section-kicker text-destructive">
              Step {deleteStep} of 2
            </p>
            <DialogTitle className="pr-7">
              {deleteStep === 1
                ? "Delete your CareerStack account?"
                : "Confirm permanent deletion"}
            </DialogTitle>
            <DialogDescription>
              {deleteStep === 1
                ? "Review what will be removed before continuing."
                : `Type DELETE to confirm that you want to permanently remove ${user.email}.`}
            </DialogDescription>
          </DialogHeader>

          {deleteStep === 1 ? (
            <>
              <div className="account-delete-summary" role="note">
                <p>This removes your sign-in and access to:</p>
                <ul>
                  <li>Your saved resume analyses and recommendations</li>
                  <li>Your matching-role views and associated account data</li>
                </ul>
              </div>
              <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                <Button type="button" variant="outline" onClick={() => closeDeleteDialog(false)}>
                  Keep my account
                </Button>
                <Button type="button" variant="destructive" onClick={() => setDeleteStep(2)}>
                  Continue to deletion
                </Button>
              </div>
            </>
          ) : (
            <form onSubmit={confirmDelete} aria-busy={deleting}>
              <div className="grid gap-2">
                <Label htmlFor="delete-confirmation">Type DELETE</Label>
                <Input
                  id="delete-confirmation"
                  value={confirmation}
                  onChange={(event) => setConfirmation(event.target.value)}
                  autoComplete="off"
                  autoCapitalize="characters"
                  spellCheck={false}
                  disabled={deleting}
                  aria-describedby="delete-confirmation-help"
                  autoFocus
                />
                <p id="delete-confirmation-help" className="text-xs leading-5 text-muted-foreground">
                  This confirmation is required to prevent accidental deletion.
                </p>
              </div>
              {deleteError && (
                <p className="form-error mt-4" role="alert">
                  {deleteError}
                </p>
              )}
              <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setDeleteStep(1);
                    setConfirmation("");
                    setDeleteError("");
                  }}
                  disabled={deleting}
                >
                  Back
                </Button>
                <Button
                  type="submit"
                  variant="destructive"
                  disabled={deleting || confirmation !== "DELETE"}
                >
                  <Trash2 aria-hidden="true" />
                  {deleting ? "Deleting account…" : "Permanently delete account"}
                </Button>
              </div>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </WorkspaceShell>
  );
}
