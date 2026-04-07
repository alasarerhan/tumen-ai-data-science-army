import React from "react";
import { cn } from "../../lib/utils";

export interface AvatarUser {
  id: string;
  name: string;
  initials: string;
}

interface AvatarProps {
  user: AvatarUser;
  size?: 24 | 32 | 40 | 48 | 64;
  className?: string;
}

const sizeClasses = {
  24: "size-6 text-[10px]",
  32: "size-8 text-xs",
  40: "size-10 text-sm",
  48: "size-12 text-sm",
  64: "size-16 text-base",
};

const AVATAR_PALETTE = [
  "bg-indigo-500",
  "bg-violet-500",
  "bg-sky-500",
  "bg-emerald-500",
  "bg-rose-500",
  "bg-amber-500",
  "bg-cyan-500",
  "bg-fuchsia-500",
];

function getAvatarColor(userId: string): string {
  let hash = 0;
  for (let i = 0; i < userId.length; i += 1) {
    hash = (hash << 5) - hash + userId.charCodeAt(i);
    hash |= 0;
  }
  const idx = Math.abs(hash) % AVATAR_PALETTE.length;
  return AVATAR_PALETTE[idx];
}

export function Avatar({ user, size = 32, className }: AvatarProps) {
  const colorClass = getAvatarColor(user.id);
  return (
    <div
      className={cn(
        "rounded-full flex items-center justify-center text-white font-semibold flex-shrink-0",
        sizeClasses[size],
        colorClass,
        className
      )}
      title={user.name}
    >
      {user.initials}
    </div>
  );
}

