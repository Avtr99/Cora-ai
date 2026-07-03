import React, { useState } from 'react';
import { sanitizeInput } from '@/lib/security';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select";
import { CHART, TEXT, NEUTRAL } from "@/lib/colors";

interface PricingChartProps {
  selectedCategory?: string;
  onCategoryChange?: (category: string) => void;
}

// Static Recharts style objects — hoisted to avoid recreating on every render
// Uses CSS variables from design system for theme consistency
const TOOLTIP_CONTENT_STYLE = {
  borderRadius: '12px',
  border: '1px solid hsl(var(--border))',
  boxShadow: 'var(--shadow-tooltip)',
  fontSize: '12px',
  padding: '10px 14px',
  fontFamily: 'Inter, sans-serif',
  backgroundColor: 'hsl(var(--background))',
};

const LEGEND_WRAPPER_STYLE = { fontSize: '12px', paddingBottom: '10px', fontWeight: 500, fontFamily: 'Inter' };

const PRICING_DATA = [
  { year: "Jun-20", agriculture: 27.86, redd: 5.70, household: 4.97, renewable: 1.30 },
  { year: "Jul-20", agriculture: 28.34, redd: 5.13, household: 4.34, renewable: 1.40 },
  { year: "Aug-20", agriculture: 29.99, redd: 4.61, household: 4.88, renewable: 1.66 },
  { year: "Sep-20", agriculture: 29.99, redd: 5.35, household: 4.64, renewable: 1.58 },
  { year: "Oct-20", agriculture: 30.00, redd: 4.53, household: 4.74, renewable: 1.63 },
  { year: "Nov-20", agriculture: 29.28, redd: 5.62, household: 4.56, renewable: 1.47 },
  { year: "Dec-20", agriculture: 26.49, redd: 4.88, household: 4.68, renewable: 1.65 },
  { year: "Jan-21", agriculture: 23.51, redd: 5.68, household: 5.44, renewable: 2.57 },
  { year: "Feb-21", agriculture: 27.07, redd: 5.84, household: 5.23, renewable: 2.38 },
  { year: "Mar-21", agriculture: 28.10, redd: 4.79, household: 5.26, renewable: 2.61 },
  { year: "Apr-21", agriculture: 28.45, redd: 5.42, household: 5.21, renewable: 2.24 },
  { year: "May-21", agriculture: 27.88, redd: 5.25, household: 5.23, renewable: 2.40 },
  { year: "Jun-21", agriculture: 27.66, redd: 7.08, household: 5.13, renewable: 2.25 },
  { year: "Jul-21", agriculture: 27.67, redd: 4.82, household: 5.33, renewable: 2.10 },
  { year: "Aug-21", agriculture: 28.30, redd: 5.88, household: 5.54, renewable: 2.63 },
  { year: "Sep-21", agriculture: 29.43, redd: 4.92, household: 5.38, renewable: 2.30 },
  { year: "Oct-21", agriculture: 28.99, redd: 4.22, household: 5.24, renewable: 2.27 },
  { year: "Nov-21", agriculture: 29.38, redd: 4.21, household: 5.49, renewable: 2.37 },
  { year: "Dec-21", agriculture: 24.95, redd: 4.46, household: 5.43, renewable: 2.37 },
  { year: "Jan-22", agriculture: 20.98, redd: 8.57, household: 9.61, renewable: 4.78 },
  { year: "Feb-22", agriculture: 19.60, redd: 12.05, household: 11.34, renewable: 7.75 },
  { year: "Mar-22", agriculture: 19.23, redd: 13.63, household: 12.54, renewable: 7.96 },
  { year: "Apr-22", agriculture: 19.63, redd: 14.25, household: 12.37, renewable: 7.26 },
  { year: "May-22", agriculture: 18.99, redd: 13.75, household: 12.08, renewable: 6.67 },
  { year: "Jun-22", agriculture: 15.41, redd: 13.05, household: 11.35, renewable: 6.24 },
  { year: "Jul-22", agriculture: 18.70, redd: 12.11, household: 11.05, renewable: 6.60 },
  { year: "Aug-22", agriculture: 19.72, redd: 11.42, household: 10.07, renewable: 5.37 },
  { year: "Sep-22", agriculture: 13.26, redd: 12.02, household: 9.84, renewable: 4.91 },
  { year: "Oct-22", agriculture: 19.73, redd: 12.92, household: 9.85, renewable: 4.52 },
  { year: "Nov-22", agriculture: 14.77, redd: 13.90, household: 9.60, renewable: 5.06 },
  { year: "Dec-22", agriculture: 18.14, redd: 10.44, household: 9.97, renewable: 4.03 },
  { year: "Jan-23", agriculture: 17.79, redd: 9.55, household: 10.25, renewable: 4.46 },
  { year: "Feb-23", agriculture: 19.55, redd: 8.75, household: 9.49, renewable: 3.66 },
  { year: "Mar-23", agriculture: 11.76, redd: 8.69, household: 9.15, renewable: 4.04 },
  { year: "Apr-23", agriculture: 17.27, redd: 8.01, household: 8.61, renewable: 3.21 },
  { year: "May-23", agriculture: 18.42, redd: 7.23, household: 8.44, renewable: 3.49 },
  { year: "Jun-23", agriculture: 17.81, redd: 7.74, household: 8.06, renewable: 3.64 },
  { year: "Jul-23", agriculture: 15.98, redd: 8.01, household: 7.61, renewable: 3.22 },
  { year: "Aug-23", agriculture: 15.15, redd: 8.18, household: 8.09, renewable: 3.27 },
  { year: "Sep-23", agriculture: 15.79, redd: 8.15, household: 7.45, renewable: 2.95 },
  { year: "Oct-23", agriculture: 18.24, redd: 8.41, household: 7.28, renewable: 2.81 },
  { year: "Nov-23", agriculture: 16.73, redd: 8.48, household: 7.17, renewable: 2.06 },
  { year: "Dec-23", agriculture: 15.95, redd: 9.10, household: 7.25, renewable: 2.34 },
  { year: "Jan-24", agriculture: 18.12, redd: 7.62, household: 7.31, renewable: 2.07 },
  { year: "Feb-24", agriculture: 18.34, redd: 7.67, household: 6.51, renewable: 2.73 },
  { year: "Mar-24", agriculture: 20.01, redd: 7.29, household: 6.83, renewable: 2.29 },
  { year: "Apr-24", agriculture: 21.34, redd: 7.69, household: 6.49, renewable: 2.04 },
  { year: "May-24", agriculture: 29.85, redd: 8.32, household: 6.37, renewable: 2.08 },
  { year: "Jun-24", agriculture: 22.98, redd: 7.28, household: 6.01, renewable: 2.30 },
  { year: "Jul-24", agriculture: 22.59, redd: 6.80, household: 6.15, renewable: 2.03 },
  { year: "Aug-24", agriculture: 16.13, redd: 7.83, household: 5.96, renewable: 2.09 },
  { year: "Sep-24", agriculture: 13.99, redd: 10.07, household: 6.21, renewable: 1.55 },
];

const CATEGORY_OPTIONS = [
  { id: "household", name: "Household Devices", color: CHART.household },
  { id: "agriculture", name: "Agriculture", color: CHART.agriculture },
  { id: "renewable", name: "Renewable Energy", color: CHART.renewable },
  { id: "redd", name: "REDD+", color: CHART.redd },
];

/**
 * PricingChart component displays historical pricing data by project type
 * Shows a line chart with multiple data series and allows filtering by project type
 */
const PricingChart: React.FC<PricingChartProps> = ({ 
  selectedCategory: externalSelectedCategory, 
  onCategoryChange 
}) => {
  // Use internal state if no external state is provided
  const [internalSelectedCategory, setInternalSelectedCategory] = useState<string>("REDD+");
  
  // Use external state if provided, otherwise use internal state
  const selectedCategory = externalSelectedCategory ?? internalSelectedCategory;
  
  // Handle category selection
  const handleCategoryChange = (value: string) => {
    const sanitizedValue = sanitizeInput(value);
    
    if (externalSelectedCategory === undefined) {
      setInternalSelectedCategory(sanitizedValue);
    }
    if (onCategoryChange) {
      onCategoryChange(sanitizedValue);
    }
  };
  
  return (
    <div className="bg-surface-card rounded-2xl border border-border-ui p-5 md:p-6 h-full flex flex-col shadow-sm">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between mb-6">
        <div className="max-w-md space-y-2">
          <h2 className="font-poppins text-base font-semibold leading-[22px] text-text-primary">Project Type and Methodology breakdown</h2>
          <p className="font-inter text-sm leading-[18px] text-text-secondary">Explore historical pricing data by project type</p>
        </div>
        
        <div className="flex flex-col gap-1.5 md:mt-0 shrink-0">
          <Select
            value={selectedCategory}
            onValueChange={handleCategoryChange}
          >
            <SelectTrigger 
              className="w-44 h-10 bg-surface-card border-border-ui rounded-lg px-4 font-inter text-sm font-medium text-text-primary focus:ring-1 focus:ring-border-ui focus:ring-offset-0 hover:border-border-ui transition-all duration-200 shadow-sm"
              aria-label="Select project category"
            >
              <span className="truncate">{selectedCategory}</span>
            </SelectTrigger>
            <SelectContent className="bg-surface-card border border-border-ui rounded-xl shadow-lg w-44 py-1">
              {CATEGORY_OPTIONS.map((cat) => (
                <SelectItem 
                  key={cat.id} 
                  value={cat.name}
                  className="font-inter text-sm text-text-secondary cursor-pointer px-3 py-2 data-[state=checked]:bg-surface-subtle data-[state=checked]:text-text-primary data-[state=checked]:font-medium hover:bg-surface-base outline-none rounded-md"
                >
                  {cat.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="font-inter text-xs leading-[14px] text-left text-text-muted">
            Last updated Sep-2024
          </div>
        </div>
      </div>

      <div className="h-[200px] md:h-[230px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={PRICING_DATA}
            margin={{ top: 0, right: 10, left: 12, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={NEUTRAL[100]} />
            <XAxis
              dataKey="year"
              tick={{ fontSize: 9, fill: TEXT.muted }}
              axisLine={false}
              tickLine={false}
              angle={-45}
              textAnchor="end"
              height={50}
              interval={3}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 11, fill: TEXT.muted }}
              domain={[0, 'auto']}
              allowDataOverflow={false}
              label={{ value: 'Price ($/t)', angle: -90, position: 'insideLeft', style: { textAnchor: 'middle', fontSize: 11, fill: TEXT.muted, fontWeight: 500 } }}
            />
            <Tooltip
              contentStyle={TOOLTIP_CONTENT_STYLE}
              formatter={(value) => [`$${value}/t`, '']}
              labelFormatter={(label) => `Vintage: ${label}`}
            />
            <Legend
              verticalAlign="top"
              height={36}
              iconType="circle"
              iconSize={10}
              wrapperStyle={LEGEND_WRAPPER_STYLE}
              formatter={(value) => <span className="text-text-primary">{value}</span>}
            />
            {/* Only show the selected category */}
            {CATEGORY_OPTIONS
              .filter(category => category.name === selectedCategory)
              .map((category) => (
                <Line
                  key={category.id}
                  type="monotone"
                  dataKey={category.id}
                  stroke={category.color}
                  strokeWidth={2}
                  dot={{ r: 0 }}
                  activeDot={{ r: 4 }}
                  name={category.name}
                />
              ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      
      <div className="font-inter text-xs leading-[16px] font-normal text-text-muted mt-4 italic">
        Prices shown are fictional and for illustrative purposes only.
      </div>
    </div>
  );
};

export default PricingChart;
