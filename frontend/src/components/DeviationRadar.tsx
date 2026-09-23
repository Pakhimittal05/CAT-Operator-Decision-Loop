import React from 'react';
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';

interface RadarProps {
  scores?: {
    efficiency_score: number;
    idling_score: number;
    duration_score: number;
    load_cycle_score: number;
    safety_score: number;
  };
  title?: string;
}

export const DeviationRadar: React.FC<RadarProps> = ({ scores, title = "Operator Performance Profile (0–100)" }) => {
  const data = [
    { dimension: 'Efficiency', score: scores ? Math.round(scores.efficiency_score) : 50, fullMark: 100 },
    { dimension: 'Idling Control', score: scores ? Math.round(scores.idling_score) : 50, fullMark: 100 },
    { dimension: 'Duration Pace', score: scores ? Math.round(scores.duration_score) : 50, fullMark: 100 },
    { dimension: 'Load Cycles', score: scores ? Math.round(scores.load_cycle_score) : 50, fullMark: 100 },
    { dimension: 'Safety Clearance', score: scores ? Math.round(scores.safety_score) : 50, fullMark: 100 },
  ];

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 flex flex-col items-center">
      <div className="text-sm font-semibold text-slate-300 mb-2 w-full text-left flex justify-between items-center">
        <span>{title}</span>
        <span className="text-xs text-amber-400 font-mono">Reference Center: 50</span>
      </div>
      <div className="w-full h-64 sm:h-72">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart cx="50%" cy="50%" outerRadius="75%" data={data}>
            <PolarGrid stroke="#334155" strokeDasharray="3 3" />
            <PolarAngleAxis
              dataKey="dimension"
              tick={{ fill: '#94a3b8', fontSize: 12 }}
            />
            <PolarRadiusAxis
              angle={90}
              domain={[0, 100]}
              tick={{ fill: '#64748b', fontSize: 10 }}
              stroke="#334155"
            />
            <Radar
              name="Skill Score"
              dataKey="score"
              stroke="#fbbf24"
              fill="#fbbf24"
              fillOpacity={0.35}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#0f172a',
                borderColor: '#334155',
                borderRadius: '0.5rem',
                fontSize: '12px',
                color: '#e2e8f0',
              }}
              formatter={(value: any) => [`${value} / 100`, 'Score']}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
      <div className="grid grid-cols-5 gap-2 w-full pt-2 border-t border-slate-800/80 text-center text-xs text-slate-400">
        <div>
          <div className="text-slate-500 text-[10px]">Efficiency</div>
          <div className="font-semibold text-amber-300">{scores ? Math.round(scores.efficiency_score) : '-'}</div>
        </div>
        <div>
          <div className="text-slate-500 text-[10px]">Idling</div>
          <div className="font-semibold text-amber-300">{scores ? Math.round(scores.idling_score) : '-'}</div>
        </div>
        <div>
          <div className="text-slate-500 text-[10px]">Duration</div>
          <div className="font-semibold text-amber-300">{scores ? Math.round(scores.duration_score) : '-'}</div>
        </div>
        <div>
          <div className="text-slate-500 text-[10px]">Cycles</div>
          <div className="font-semibold text-amber-300">{scores ? Math.round(scores.load_cycle_score) : '-'}</div>
        </div>
        <div>
          <div className="text-slate-500 text-[10px]">Safety</div>
          <div className="font-semibold text-amber-300">{scores ? Math.round(scores.safety_score) : '-'}</div>
        </div>
      </div>
    </div>
  );
};
