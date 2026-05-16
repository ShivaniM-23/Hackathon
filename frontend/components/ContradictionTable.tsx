"use client";

import React from 'react';
import { Activity, AlertTriangle, CheckCircle, Info } from 'lucide-react';

interface Contradiction {
  field: string;
  claimed: string;
  evidence: string;
  severity: "HIGH" | "MEDIUM" | "LOW";
}

interface ContradictionTableProps {
  contradictions: Contradiction[];
  redFlags?: string[];
}

const ContradictionTable: React.FC<ContradictionTableProps> = ({ contradictions, redFlags = [] }) => {
  const safeContradictions = contradictions ?? [];
  const safeRedFlags = redFlags ?? [];

  if (safeContradictions.length === 0 && safeRedFlags.length === 0) {
    return (
      <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-12 text-center">
        <div className="w-16 h-16 bg-emerald-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
          <CheckCircle className="text-emerald-500" size={32} />
        </div>
        <h3 className="text-lg font-semibold text-neutral-200">Digital Footprint Verified</h3>
        <p className="text-sm text-neutral-500 mt-2">No major contradictions or red flags detected in the digital traces.</p>
      </div>
    );
  }

  if (safeContradictions.length === 0) {
    return (
      <div className="bg-neutral-900 border border-yellow-500/20 rounded-2xl p-12 text-center">
        <div className="w-16 h-16 bg-yellow-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
          <AlertTriangle className="text-yellow-400" size={32} />
        </div>
        <h3 className="text-lg font-semibold text-neutral-200">Digital Footprint Needs Review</h3>
        <p className="text-sm text-neutral-500 mt-2">
          No direct contradictions were found, but scoring red flags were detected in the broader footprint.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-2xl overflow-hidden shadow-xl">
      <div className="p-6 border-b border-neutral-800 flex justify-between items-center">
        <h3 className="font-semibold flex items-center gap-2">
          <Activity size={18} className="text-blue-400" />
          Conflict Verification Engine
        </h3>
        <div className="text-[10px] bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded font-bold uppercase tracking-wider">
          {safeContradictions.length} Issues Found
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-neutral-950/50 text-[10px] text-neutral-500 uppercase tracking-widest">
              <th className="px-6 py-4 font-semibold">Analyzed Field</th>
              <th className="px-6 py-4 font-semibold">Claimed (Website)</th>
              <th className="px-6 py-4 font-semibold">Evidence (External)</th>
              <th className="px-6 py-4 text-right">Severity</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-800/50">
            {safeContradictions.map((item, i) => (
              <tr 
                key={i} 
                className={`transition-colors group ${
                  item.severity === 'HIGH' ? 'bg-red-500/5 hover:bg-red-500/10' :
                  item.severity === 'MEDIUM' ? 'bg-yellow-500/5 hover:bg-yellow-500/10' :
                  'bg-emerald-500/5 hover:bg-emerald-500/10'
                }`}
              >
                <td className="px-6 py-4">
                  <div className="flex items-center gap-2">
                    <span className={`w-1 h-1 rounded-full ${
                      item.severity === 'HIGH' ? 'bg-red-500' :
                      item.severity === 'MEDIUM' ? 'bg-yellow-500' :
                      'bg-emerald-500'
                    }`} />
                    <span className="font-medium text-neutral-300 text-sm">
                      {item.field?.toUpperCase()}
                    </span>
                  </div>
                </td>
                <td className="px-6 py-4 text-neutral-400 text-sm">{item.claimed}</td>
                <td className="px-6 py-4 text-neutral-200 text-sm font-medium">{item.evidence}</td>
                <td className="px-6 py-4 text-right">
                  <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold border ${
                    item.severity === 'HIGH' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                    item.severity === 'MEDIUM' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                    'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                  }`}>
                    {item.severity === 'HIGH' && <AlertTriangle size={10} />}
                    {item.severity}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="p-4 bg-neutral-950/30 border-t border-neutral-800/50 flex items-center gap-2 text-[10px] text-neutral-500 italic">
        <Info size={12} />
        Verification performed by ShadowTrace SLM using WHOIS, LinkedIn, and Web-scraping cross-referencing.
      </div>
    </div>
  );
};

export default ContradictionTable;
