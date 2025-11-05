import React from 'react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import styles from './LiveLineChart.module.css'; // Import CSS Module

// Register Chart.js components (keep as is)
ChartJS.register(
  CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend
);

const LiveLineChart = ({ title, data }) => {

  const options = {
    responsive: true,
    maintainAspectRatio: false, // Important for fitting container
    plugins: {
      legend: {
        position: 'top',
        labels: {
          color: 'var(--text-secondary)', // Use CSS Variable
          boxWidth: 12,
          padding: 15
         }
      },
      title: {
        display: true,
        text: title,
        color: 'var(--text-primary)', // Use CSS Variable
        font: { size: 16, weight: '600' } // Adjust font
      },
      tooltip: {
        backgroundColor: 'var(--bg-elevated)', // Use CSS Variable
        titleColor: 'var(--text-primary)',
        bodyColor: 'var(--text-secondary)',
        borderColor: 'var(--border-default)',
        borderWidth: 1,
        padding: 10,
        boxPadding: 4
      }
    },
    scales: {
      x: {
        ticks: { color: 'var(--text-tertiary)' }, // Use CSS Variable
        grid: { color: 'var(--border-subtle)' } // Use CSS Variable
      },
      y: {
        ticks: { color: 'var(--text-tertiary)' }, // Use CSS Variable
        grid: { color: 'var(--border-subtle)' }, // Use CSS Variable
        beginAtZero: true // Sensible default, can be overridden if needed
      }
    },
    // Keep animation settings for live updates
    animation: { duration: 0 },
    hover: { animationDuration: 0 },
    responsiveAnimationDuration: 0,
     elements: {
        line: {
            tension: 0.1 // Slight curve
        },
        point:{
            radius: 2 // Smaller points
        }
    }
  };

  // Adjust y-axis if title indicates R²
  if (title?.toLowerCase().includes('r²')) {
    options.scales.y.beginAtZero = false; // R² can be negative
  }

  return (
    // Apply CSS module style to the wrapper
    <div className={styles.chartWrapper}>
      <Line options={options} data={data} />
    </div>
  );
};

export default LiveLineChart;