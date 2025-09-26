import React, { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Grid,
  Paper,
  LinearProgress,
  Alert,
} from '@mui/material';
import {
  PlayArrow,
  Refresh,
  Assessment,
} from '@mui/icons-material';

import OptimizationControl from './OptimizationControl';
import RosterVisualization from './RosterVisualization';
import PostRosterInsights from './PostRosterInsights';

const DashboardView = ({
  currentRoster,
  baselineRoster,
  flights,
  crew,
  loading,
  optimizationProgress,
  onOptimize,
  onReset,
}) => {
  const [selectedDate, setSelectedDate] = useState(null);
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {/* Optimization Control Panel */}
      <OptimizationControl
        onOptimize={onOptimize}
        loading={loading}
        hasBaseline={!!baselineRoster}
        onReset={onReset}
      />

      {/* Progress Indicator */}
      {optimizationProgress && optimizationProgress.status === 'running' && (
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <PlayArrow sx={{ mr: 1, color: 'primary.main' }} />
              <Typography variant="h6" sx={{ color: '#1A1A1A' }}>
                Optimization in Progress
              </Typography>
            </Box>
            <LinearProgress 
              variant="determinate" 
              value={optimizationProgress.progress || 0} 
              sx={{ mb: 1 }}
            />
            <Typography variant="body2" color="text.secondary">
              {optimizationProgress.progress || 0}% Complete
            </Typography>
          </CardContent>
        </Card>
      )}

      {/* Current Roster Visualization */}
      {currentRoster && (
        <>
          <RosterVisualization
            roster={currentRoster}
            title="Current Roster"
            showKPIs={true}
            controlledDate={selectedDate}
            onChangeDate={setSelectedDate}
          />
          {/* Post-Roster Insights: Standby, Discretion, Overtime */}
          {currentRoster.insights && (
            <Box sx={{ mt: 3 }}>
              <PostRosterInsights insights={currentRoster.insights} />
            </Box>
          )}
        </>
      )}

      {/* No Data State */}
      {!currentRoster && !loading && (
        <Card>
          <CardContent>
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <Assessment sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" color="text.secondary" gutterBottom>
                No Roster Data Available
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Run an optimization to generate crew assignments and view the roster
              </Typography>
            </Box>
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

export default DashboardView;
