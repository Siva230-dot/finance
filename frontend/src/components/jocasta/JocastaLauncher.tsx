import { AnimatePresence, motion } from "framer-motion";
import { Maximize2, Plus, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { ChatView, JocastaAvatar } from "./ChatView";
import { useJocasta } from "./useJocasta";

export function JocastaLauncher() {
  const [open, setOpen] = useState(false);
  const chat = useJocasta();
  return (
    <>
      <AnimatePresence>
        {open && (
          <motion.div
            role="dialog" aria-label="JOCASTA assistant"
            initial={{ opacity: 0, y: 24, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 24, scale: 0.97 }}
            transition={{ type: "spring", damping: 26, stiffness: 300 }}
            className="fixed inset-x-0 bottom-0 z-50 flex h-[85vh] flex-col overflow-hidden rounded-t-2xl border border-line bg-bg shadow-lift sm:inset-x-auto sm:bottom-24 sm:right-6 sm:h-[640px] sm:max-h-[calc(100vh-8rem)] sm:w-[420px] sm:rounded-2xl"
          >
            <header className="flex items-center justify-between bg-forest px-4 py-3 text-onforest dark:bg-[#1c261f]">
              <div className="flex items-center gap-3">
                <JocastaAvatar size={34} />
                <div>
                  <p className="font-serif text-lg leading-none tracking-[0.12em]">JOCASTA</p>
                  <p className="mt-1 text-[10.5px] uppercase tracking-[0.2em] text-[#C2A56E]">Personal finance assistant</p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <button onClick={chat.reset} className="rounded p-1.5 text-onforest/70 hover:bg-white/10 hover:text-onforest" aria-label="New conversation" title="New conversation"><Plus className="h-4 w-4" /></button>
                <Link to="/app/jocasta" onClick={() => setOpen(false)} className="rounded p-1.5 text-onforest/70 hover:bg-white/10 hover:text-onforest" aria-label="Open full screen" title="Open full screen"><Maximize2 className="h-4 w-4" /></Link>
                <button onClick={() => setOpen(false)} className="rounded p-1.5 text-onforest/70 hover:bg-white/10 hover:text-onforest" aria-label="Close assistant"><X className="h-4 w-4" /></button>
              </div>
            </header>
            <div className="min-h-0 flex-1"><ChatView chat={chat} compact /></div>
          </motion.div>
        )}
      </AnimatePresence>
      <motion.button
        onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-label={open ? "Close JOCASTA" : "Open JOCASTA assistant"}
        className="group fixed bottom-5 right-5 z-50 flex items-center gap-2.5 rounded-full border border-gold/60 bg-forest py-2 pl-2 pr-4 text-onforest shadow-lift sm:bottom-6 sm:right-6"
        whileHover={{ y: -2 }} whileTap={{ scale: 0.97 }} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}
      >
        <JocastaAvatar size={34} />
        <span className="font-serif text-[15px] tracking-[0.14em]">{open ? "Close" : "JOCASTA"}</span>
        {!open && <span className="absolute -right-0.5 -top-0.5 h-3 w-3 rounded-full border-2 border-bg bg-gold" aria-hidden />}
      </motion.button>
    </>
  );
}
