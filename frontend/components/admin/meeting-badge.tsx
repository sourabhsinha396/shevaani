import { AlertTriangle, CheckCircle2, Clock } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { MeetingStatus } from "@/lib/types";

/**
 * Meet creation is the one part of the system that depends on a third party and
 * can fail quietly, so its state is shown wherever a session is shown — never
 * inferred from the session's own status.
 */
export function MeetingBadge({
  status,
  error,
}: {
  status: MeetingStatus | null;
  error?: string | null;
}) {
  if (status === "ready") {
    return (
      <Badge variant="success" title="Meet link created">
        <CheckCircle2 /> Meet ready
      </Badge>
    );
  }
  if (status === "failed") {
    return (
      <Badge variant="destructive" title={error ?? "Meet creation failed"}>
        <AlertTriangle /> Meet failed
      </Badge>
    );
  }
  return (
    <Badge variant="warning">
      <Clock /> Meet pending
    </Badge>
  );
}
