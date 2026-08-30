"use client";
import { motion } from "framer-motion";
import type { Mission } from "./types";
export function MissionCard({ mission, selected, onSelect }: { mission: Mission; selected: boolean; onSelect: () => void }) { return <motion.button layout initial={{ opacity: 0 }} animate={{ opacity: 1 }} className={`mission-card ${selected ? "selected" : ""}`} onClick={onSelect}><span className={`mission-status ${mission.lifecycle}`}>{mission.lifecycle}</span><strong>{mission.title}</strong><p>{mission.description}</p><footer>{mission.priority ?? "medium"} priority · {new Date(mission.created_at).toLocaleString()}</footer></motion.button>; }
