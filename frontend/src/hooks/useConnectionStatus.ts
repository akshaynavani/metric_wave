import { useEffect, useState } from "react";

import { streamClient } from "../lib/stream";
import type { ConnectionStatus } from "../lib/types";

export function useConnectionStatus(): ConnectionStatus {
  const [status, setStatus] = useState<ConnectionStatus>(streamClient.getStatus());
  useEffect(() => streamClient.onStatus(setStatus), []);
  return status;
}
