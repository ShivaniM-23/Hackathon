"use client";

import React from "react";
import { MessageCircle, Star, TrendingDown, TrendingUp, AlertTriangle, ShieldCheck } from "lucide-react";

interface ReviewsPanelProps {
  report: {
    raw_data_summary?: {
      reviews?: unknown;
      discovered_links?: Record<string, string | null>;
    };
    reviews?: unknown;
    discovered_links?: Record<string, string | null>;
  };
}

interface RedditPost {
  title: string;
}

interface Reviews {
  overall_sentiment?: string;
  reddit?: {
    mentions?: number;
    negative_posts?: RedditPost[];
    positive_posts?: RedditPost[];
  };
  trustpilot?: {
    rating?: number | null;
    found?: boolean;
  };
  glassdoor?: {
    rating?: number | null;
  };
  google_news_sentiment?: {
    total?: number;
    negative?: number;
    positive?: number;
  };
}

const ReviewsPanel: React.FC<ReviewsPanelProps> = ({ report }) => {
  const reviews = (report?.raw_data_summary?.reviews || report?.reviews || {}) as Reviews;
  const discovered = report?.raw_data_summary?.discovered_links || report?.discovered_links || {};
  
  const sentiment = reviews.overall_sentiment || "NO_DATA";
  const reddit = {
    mentions: reviews.reddit?.mentions ?? 0,
    negative_posts: reviews.reddit?.negative_posts ?? [],
    positive_posts: reviews.reddit?.positive_posts ?? [],
  };
  const tp = reviews.trustpilot || { rating: null, found: false };
  const gd = reviews.glassdoor || { rating: null };
  const news = reviews.google_news_sentiment || { total: 0, negative: 0, positive: 0 };

  const getSentimentColor = (s: string) => {
    switch (s) {
      case "POSITIVE": return "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
      case "NEGATIVE": return "text-red-400 bg-red-500/10 border-red-500/20";
      case "MIXED": return "text-amber-400 bg-amber-500/10 border-amber-500/20";
      default: return "text-neutral-400 bg-neutral-500/10 border-neutral-500/20";
    }
  };

  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6 shadow-xl h-full flex flex-col">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-sm font-bold text-neutral-400 uppercase tracking-widest flex items-center gap-2">
          <MessageCircle size={18} className="text-blue-400" />
          Public Sentiment Analysis
        </h3>
        <div className={`px-3 py-1 rounded-full border text-[10px] font-bold uppercase tracking-tighter ${getSentimentColor(sentiment)}`}>
          {sentiment}
        </div>
      </div>

      {/* Discovery Badge Bar */}
      <div className="flex gap-2 mb-6 flex-wrap">
        {discovered.linkedin && <div className="px-2 py-1 bg-blue-500/10 border border-blue-500/20 rounded text-[10px] text-blue-400 flex items-center gap-1">✅ LinkedIn</div>}
        {discovered.twitter && <div className="px-2 py-1 bg-sky-500/10 border border-sky-500/20 rounded text-[10px] text-sky-400 flex items-center gap-1">✅ Twitter</div>}
        {discovered.github && <div className="px-2 py-1 bg-neutral-100/10 border border-neutral-100/20 rounded text-[10px] text-neutral-100 flex items-center gap-1">✅ GitHub</div>}
        {discovered.crunchbase && <div className="px-2 py-1 bg-neutral-100/10 border border-neutral-100/20 rounded text-[10px] text-neutral-100 flex items-center gap-1">✅ Crunchbase</div>}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 flex-1">
        {/* Reddit Section */}
        <div className="bg-neutral-950 rounded-xl border border-neutral-800 p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-neutral-500 uppercase tracking-wide">Reddit Presence</span>
            <span className="text-xs text-neutral-300">{reddit.mentions} Mentions</span>
          </div>
          {reddit.negative_posts.length > 0 ? (
            <div className="space-y-2">
              {reddit.negative_posts.slice(0, 2).map((p: RedditPost, i: number) => (
                <div key={i} className="flex gap-2 items-start bg-red-500/5 p-2 rounded border border-red-500/10">
                  <TrendingDown size={14} className="text-red-400 mt-0.5 flex-shrink-0" />
                  <p className="text-[11px] text-red-200 line-clamp-2 leading-tight">{p.title}</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="h-16 flex items-center justify-center border border-dashed border-neutral-800 rounded bg-neutral-900/20">
              <span className="text-[10px] text-neutral-600">No negative mentions detected</span>
            </div>
          )}
        </div>

        {/* Ratings Section */}
        <div className="bg-neutral-950 rounded-xl border border-neutral-800 p-4 flex flex-col gap-3">
           <div className="flex items-center justify-between">
              <span className="text-[11px] text-neutral-500 uppercase font-bold tracking-tight">Trustpilot</span>
              {tp.rating ? (
                <div className="flex items-center gap-1">
                  <span className={`text-xs font-bold ${tp.rating >= 4 ? 'text-emerald-400' : 'text-red-400'}`}>{tp.rating}/5</span>
                  <Star size={12} className={tp.rating >= 4 ? 'text-emerald-400 fill-emerald-400' : 'text-red-400 fill-red-400'} />
                </div>
              ) : <span className="text-[10px] text-neutral-600 italic">Not found</span>}
           </div>

           <div className="flex items-center justify-between">
              <span className="text-[11px] text-neutral-500 uppercase font-bold tracking-tight">Glassdoor</span>
              {gd.rating ? (
                <div className="flex items-center gap-1">
                  <span className="text-xs font-bold text-blue-400">{gd.rating}/5</span>
                  <Star size={12} className="text-blue-400 fill-blue-400" />
                </div>
              ) : <span className="text-[10px] text-neutral-600 italic">Not found</span>}
           </div>

           <div className="flex items-center justify-between border-t border-neutral-800 pt-2 mt-1">
              <span className="text-[11px] text-neutral-500 uppercase font-bold tracking-tight">Search Sentiment</span>
              <div className="flex gap-2">
                <span className="text-[10px] text-emerald-500 flex items-center gap-0.5"><TrendingUp size={10}/> {news.positive}</span>
                <span className="text-[10px] text-red-500 flex items-center gap-0.5"><TrendingDown size={10}/> {news.negative}</span>
              </div>
           </div>
        </div>
      </div>

      <div className="mt-4 p-3 bg-blue-500/5 border border-blue-500/10 rounded-xl flex items-center gap-3">
        {sentiment === "NEGATIVE" ? (
          <AlertTriangle size={20} className="text-red-500" />
        ) : (
          <ShieldCheck size={20} className="text-blue-500" />
        )}
        <p className="text-[10px] text-neutral-400 leading-relaxed">
          {sentiment === "NEGATIVE" 
            ? "WARNING: Community sentiment is significantly negative. High risk of fraudulent activity or poor customer experience."
            : sentiment === "POSITIVE"
            ? "TRUSTED: Strong positive community footprint across Reddit and review platforms."
            : "UNVERIFIED: Limited public discourse. Use caution as lack of history is common in shell companies."
          }
        </p>
      </div>
    </div>
  );
};

export default ReviewsPanel;
