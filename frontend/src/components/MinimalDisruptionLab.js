import React, { useState } from 'react';
import { Box, Tabs, Tab } from '@mui/material';
import DisruptionSimulator from './DisruptionSimulator';
import WhatIfComparison from './WhatIfComparison';
import LLMDisruptionChat from './LLMDisruptionChat';

const MinimalDisruptionLab = ({ flights, crew, baselineRoster, currentRoster, whatIfResults, onRunScenario, loading }) => {
  const [tab, setTab] = useState(0);
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Box>
        <Tabs value={tab} onChange={(e, v) => setTab(v)}>
          <Tab label="Manual What-If" />
          <Tab label="LLM Disruption Chat" />
        </Tabs>
      </Box>

      {tab === 0 && (
        <>
          {baselineRoster && (
            <DisruptionSimulator
              flights={flights}
              crew={crew}
              onRunScenario={onRunScenario}
              loading={loading}
            />
          )}

          {whatIfResults && (
            <WhatIfComparison
              beforeRoster={baselineRoster}
              afterRoster={currentRoster}
              changes={whatIfResults.changes}
            />
          )}
        </>
      )}

      {tab === 1 && (
        <>
          <LLMDisruptionChat
            flights={flights}
            crew={crew}
            onParsed={() => { /* no manual list in minimal view */ }}
            onRunScenario={onRunScenario}
            loading={loading}
          />
          {whatIfResults && (
            <WhatIfComparison
              beforeRoster={baselineRoster}
              afterRoster={currentRoster}
              changes={whatIfResults.changes}
            />
          )}
        </>
      )}
    </Box>
  );
};

export default MinimalDisruptionLab;
