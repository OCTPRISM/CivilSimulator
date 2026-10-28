"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import {
  getInvitePreview,
  getPlayerCatalog,
  joinSession,
  type CharacterVariant,
  type PlayerCatalog,
} from "@/lib/api";
import type { RoleSkinId } from "@/lib/characterFigures";
import { setBoundPlayerId } from "@/lib/playIdentity";
import CharacterPicker from "@/components/CharacterPicker";
import { useI18n } from "@/lib/i18n";

export default function JoinRoomPage({ params }: { params: { sid: string } }) {
  const sid = params.sid;
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { t } = useI18n();
  const [worldName, setWorldName] = useState<string>("");
  const [seedKey, setSeedKey] = useState<string>("");
  const [catalog, setCatalog] = useState<PlayerCatalog | null>(null);
  const [description, setDescription] = useState("一位路过的旅人，想见识这座城的风土人情。");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [roster, setRoster] = useState(0);
  const [maxPlayers, setMaxPlayers] = useState<number | null>(null);
  const [previewReady, setPreviewReady] = useState(false);
  const [alreadyMember, setAlreadyMember] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace(`/login?next=/join/${sid}`);
    }
  }, [authLoading, user, router, sid]);

  useEffect(() => {
    if (!user) return;
    setErr(null);
    getInvitePreview(sid)
      .then(async (j) => {
        setWorldName(j.world_name || sid);
        setRoster(j.players || 1);
        setMaxPlayers(j.max_players ?? null);
        const sk = (j.seed_key || "").trim();
        setSeedKey(sk);
        if (sk) {
          try {
            const cat = await getPlayerCatalog(sk);
            setCatalog(cat);
          } catch {
            setCatalog(null);
          }
        } else {
          setCatalog(null);
        }
        setAlreadyMember(Boolean(j.already_member));
        setPreviewReady(true);
        if (j.already_member) {
          router.replace(`/play/${sid}`);
        }
      })
      .catch((e) => {
        setPreviewReady(false);
        setErr(e instanceof Error ? e.message : t("join.missing"));
      });
  }, [sid, user, router]);

  async function onConfirm(
    categoryKey: string,
    variant: CharacterVariant,
    skin: RoleSkinId,
    equippedProps: string[] = [],
    outfitStyle = "default",
  ) {
    setLoading(true);
    setErr(null);
    try {
      const { session, player_id } = await joinSession(sid, {
        category_key: categoryKey,
        variant_key: variant.key,
        skin,
        equipped_props: equippedProps,
        outfit_style: outfitStyle,
        description: `${variant.name}。${variant.persona || description}`,
      });
      setBoundPlayerId(session.id, player_id);
      sessionStorage.setItem(`sess_${session.id}`, JSON.stringify(session));
      router.push(`/play/${session.id}?pid=${encodeURIComponent(player_id)}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : t("join.fail"));
      setLoading(false);
    }
  }

  async function onJoinFallback() {
    setLoading(true);
    setErr(null);
    try {
      const { session, player_id } = await joinSession(sid, { description });
      setBoundPlayerId(session.id, player_id);
      sessionStorage.setItem(`sess_${session.id}`, JSON.stringify(session));
      router.push(`/play/${session.id}?pid=${encodeURIComponent(player_id)}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : t("join.fail"));
      setLoading(false);
    }
  }

  if (authLoading || !user || alreadyMember) {
    return (
      <main className="min-h-screen flex items-center justify-center opacity-60">
        {alreadyMember ? t("join.already") : t("common.verifying")}
      </main>
    );
  }

  const hasCatalog = Boolean(catalog?.categories?.length && seedKey && !alreadyMember);

  return (
    <main className="min-h-screen flex flex-col items-center px-4 py-10 bg-stone-950 text-stone-100">
      <div className={`w-full ${hasCatalog ? "max-w-3xl" : "max-w-lg"}`}>
        <Link href="/" className="text-sm opacity-60 hover:opacity-100">← {t("common.back")}</Link>
        <h1 className="mt-6 font-serif text-2xl text-amber-50">{t("join.title")}</h1>
        <p className="mt-2 text-sm opacity-70">
          {previewReady
            ? t("join.inWorld", { name: worldName || "…", n: maxPlayers ? `${roster}/${maxPlayers}` : roster })
            : t("join.reading")}
        </p>
        <p className="mt-2 text-[11px] text-amber-200/65 leading-relaxed">
          {t("join.hint")}
        </p>

        {err && <p className="mt-3 text-sm text-rose-300">{err}</p>}

        {hasCatalog ? (
          <div className="mt-8">
            <CharacterPicker
              categories={catalog!.categories}
              seedKey={seedKey}
              seedName={worldName || seedKey}
              loading={loading || !previewReady}
              confirmLabel={t("join.confirm")}
              onConfirm={onConfirm}
            />
          </div>
        ) : (
          <>
            <label className="block mt-8 text-xs uppercase tracking-widest opacity-60">
              {t("join.who")}
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              className="mt-2 w-full rounded-lg border border-stone-700 bg-stone-900/80 px-3 py-2 text-sm
                         focus:outline-none focus:border-amber-500/60"
              placeholder={t("join.whoPh")}
            />

            <button
              type="button"
              disabled={loading || !previewReady || Boolean(err) || alreadyMember}
              onClick={onJoinFallback}
              className="mt-6 w-full py-2.5 rounded-lg bg-amber-500/90 text-stone-900 font-semibold
                         disabled:opacity-40 hover:bg-amber-400"
            >
              {loading ? t("join.joining") : t("join.enter")}
            </button>
          </>
        )}
      </div>
    </main>
  );
}
