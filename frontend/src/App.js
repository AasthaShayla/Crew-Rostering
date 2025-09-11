import React, { useState, useEffect } from 'react';
import {
  ThemeProvider,
  createTheme,
  CssBaseline,
  Container,
  AppBar,
  Toolbar,
  Typography,
  Box,
  Alert,
  Snackbar,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Divider,
  IconButton,
} from '@mui/material';
import { LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import {
  FlightTakeoff,
  Person,
  Warning,
  Dashboard,
  Cloud,
  Menu as MenuIcon,
} from '@mui/icons-material';

import { apiService, connectSocket, disconnectSocket } from './services/api';
import FlightWiseView from './components/FlightWiseView';
import CrewWiseView from './components/CrewWiseView';
import DisruptionManagement from './components/DisruptionManagement';
import DashboardView from './components/DashboardView';
import WeatherCalendarView from './components/WeatherCalendarView';

// Custom IndiGo-style flight icon
const IndigoFlightIcon = ({ sx = {} }) => (
  <Box
    sx={{
      width: 20,
      height: 20,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      ...sx
    }}
  >
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M21 16V14L13 9V3.5C13 2.67 12.33 2 11.5 2S10 2.67 10 3.5V9L2 14V16L10 13.5V19L8 20.5V22L11.5 21L15 22V20.5L13 19V13.5L21 16Z"
        fill="#003DA5"
      />
    </svg>
  </Box>
);

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#003DA5',
      light: '#0078D7',
      dark: '#002A73',
    },
    secondary: {
      main: '#0078D7',
      light: '#4A9FE7',
      dark: '#005A9E',
    },
    background: {
      default: '#E6F0FA',
      paper: '#FFFFFF',
    },
    text: {
      primary: '#1A1A1A',
      secondary: '#4D4D4D',
    },
    divider: '#F5F7FA',
    success: {
      main: '#2E8B57',
      light: '#4CAF50',
      dark: '#1B5E20',
    },
    warning: {
      main: '#FFB020',
      light: '#FFC107',
      dark: '#F57C00',
    },
    error: {
      main: '#D93025',
      light: '#F44336',
      dark: '#C62828',
    },
  },
  typography: {
    h4: {
      fontWeight: 600,
      color: '#1A1A1A',
    },
    h6: {
      fontWeight: 500,
      color: '#1A1A1A',
    },
    body1: {
      color: '#1A1A1A',
    },
    body2: {
      color: '#4D4D4D',
    },
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: '8px',
          textTransform: 'none',
          fontWeight: 500,
          '&:hover': {
            backgroundColor: 'rgba(0, 120, 215, 0.1)',
            transform: 'translateY(-1px)',
            transition: 'all 0.2s ease-in-out',
            boxShadow: '0 4px 12px rgba(0, 120, 215, 0.2)',
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundColor: '#FFFFFF',
          border: '1px solid #F5F7FA',
          borderRadius: '12px',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)',
          '&:hover': {
            borderColor: '#0078D7',
            boxShadow: '0 8px 32px rgba(0, 120, 215, 0.15)',
            transition: 'all 0.3s ease-in-out',
            transform: 'translateY(-2px)',
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundColor: '#FFFFFF',
          border: '1px solid #F5F7FA',
          borderRadius: '12px',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)',
        },
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: {
          borderRadius: '8px',
          margin: '2px 0',
          '&:hover': {
            backgroundColor: 'rgba(0, 120, 215, 0.1)',
            borderLeft: '3px solid #0078D7',
            transition: 'all 0.2s ease-in-out',
          },
          '&.Mui-selected': {
            backgroundColor: 'rgba(0, 120, 215, 0.2)',
            borderLeft: '3px solid #003DA5',
            '&:hover': {
              backgroundColor: 'rgba(0, 120, 215, 0.3)',
            },
          },
        },
      },
    },
  },
});

function App() {
  const [currentRoster, setCurrentRoster] = useState(null);
  const [baselineRoster, setBaselineRoster] = useState(null);
  const [flights, setFlights] = useState([]);
  const [crew, setCrew] = useState([]);
  const [loading, setLoading] = useState(false);
  const [optimizationProgress, setOptimizationProgress] = useState(null);
  const [whatIfResults, setWhatIfResults] = useState(null);
  const [notification, setNotification] = useState({ open: false, message: '', severity: 'info' });
  const [activeView, setActiveView] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Socket connection for real-time updates
  useEffect(() => {
    const socket = connectSocket();
    
    socket.on('optimization_progress', async (data) => {
      setOptimizationProgress(data);
      if (data.status === 'completed') {
        setCurrentRoster(data.result);
        setBaselineRoster(data.result);
        // Reload latest flights/crew so disruption dropdowns are populated
        try {
          const [flightsRes, crewRes] = await Promise.all([
            apiService.getFlights(),
            apiService.getCrew(),
          ]);
          setFlights(flightsRes.data.flights || []);
          setCrew(crewRes.data.crew || []);
        } catch (e) {
          console.error('Failed refreshing data after optimization:', e);
        }
        setLoading(false);
        showNotification('Optimization completed successfully!', 'success');
      } else if (data.status === 'failed') {
        setLoading(false);
        showNotification(`Optimization failed: ${data.error}`, 'error');
      }
    });

    socket.on('reoptimization_complete', async (data) => {
      setWhatIfResults(data);
      setCurrentRoster(data.after);
      // Ensure disruption dropdowns stay fresh with any data changes
      try {
        const [flightsRes, crewRes] = await Promise.all([
          apiService.getFlights(),
          apiService.getCrew(),
        ]);
        setFlights(flightsRes.data.flights || []);
        setCrew(crewRes.data.crew || []);
      } catch (e) {
        console.error('Failed refreshing data after reoptimization:', e);
      }
      setLoading(false);
      showNotification('What-if scenario completed!', 'success');
    });

    return () => {
      disconnectSocket();
    };
  }, []);

  // Load initial data
  useEffect(() => {
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    try {
      const [flightsRes, crewRes] = await Promise.all([
        apiService.getFlights(),
        apiService.getCrew(),
      ]);
      
      setFlights(flightsRes.data.flights || []);
      setCrew(crewRes.data.crew || []);
    } catch (error) {
      console.error('Error loading initial data:', error);
      showNotification('Error loading data. Please refresh the page.', 'error');
    }
  };

  const showNotification = (message, severity = 'info') => {
    setNotification({ open: true, message, severity });
  };

  const handleCloseNotification = () => {
    setNotification({ ...notification, open: false });
  };

  const handleOptimize = async (params) => {
    setLoading(true);
    setOptimizationProgress({ status: 'running', progress: 0 });
    setWhatIfResults(null);
    
    try {
      const response = await apiService.optimize(params);
      if (response.data.success) {
        showNotification('Optimization started...', 'info');
      }
    } catch (error) {
      setLoading(false);
      showNotification('Failed to start optimization', 'error');
    }
  };

  const handleWhatIfScenario = async (disruptions) => {
    if (!baselineRoster) {
      showNotification('Please run initial optimization first', 'warning');
      return;
    }

    setLoading(true);
    
    try {
      const response = await apiService.reoptimize(disruptions);
      if (response.data.success) {
        showNotification('What-if scenario started...', 'info');
      }
    } catch (error) {
      setLoading(false);
      showNotification('Failed to run what-if scenario', 'error');
    }
  };

  const handleResetToBaseline = () => {
    setCurrentRoster(baselineRoster);
    setWhatIfResults(null);
    showNotification('Reset to baseline roster', 'info');
  };

  const handleViewChange = (viewIndex) => {
    setActiveView(viewIndex);
  };

  const toggleSidebar = () => {
    setSidebarOpen(!sidebarOpen);
  };

  const renderContent = () => {
    switch (activeView) {
      case 0:
        return (
          <DashboardView
            currentRoster={currentRoster}
            baselineRoster={baselineRoster}
            flights={flights}
            crew={crew}
            loading={loading}
            optimizationProgress={optimizationProgress}
            onOptimize={handleOptimize}
            onReset={handleResetToBaseline}
          />
        );
      case 1:
        return (
          <FlightWiseView
            flights={flights}
            currentRoster={currentRoster}
            crew={crew}
          />
        );
      case 2:
        return (
          <CrewWiseView
            crew={crew}
            currentRoster={currentRoster}
            flights={flights}
          />
        );
      case 3:
        return (
          <DisruptionManagement
            flights={flights}
            crew={crew}
            baselineRoster={baselineRoster}
            currentRoster={currentRoster}
            whatIfResults={whatIfResults}
            onRunScenario={handleWhatIfScenario}
            loading={loading}
          />
        );
      case 4:
        return (
          <WeatherCalendarView />
        );
      default:
        return null;
    }
  };

  const menuItems = [
    { text: 'Dashboard', icon: <Dashboard />, index: 0 },
    { text: 'Flight View', icon: <IndigoFlightIcon />, index: 1 },
    { text: 'Crew View', icon: <Person />, index: 2 },
    { text: 'Disruption Lab', icon: <Warning />, index: 3 },
    { text: 'Weather Forecast', icon: <Cloud />, index: 4 },
  ];

  return (
    <ThemeProvider theme={theme}>
      <LocalizationProvider dateAdapter={AdapterDayjs}>
        <CssBaseline />
        
        <Box sx={{ display: 'flex' }}>
          {/* Sidebar */}
          <Drawer
            variant="persistent"
            anchor="left"
            open={sidebarOpen}
            sx={{
              width: sidebarOpen ? 220 : 0,
              flexShrink: 0,
              '& .MuiDrawer-paper': {
                width: 220,
                boxSizing: 'border-box',
                backgroundColor: '#FFFFFF',
                borderRight: '1px solid #F5F7FA',
                transition: 'width 0.3s ease-in-out',
                boxShadow: '2px 0 8px rgba(0, 0, 0, 0.1)',
              },
            }}
          >
            <Box sx={{ p: 1.5 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6" sx={{ color: '#003DA5', fontWeight: 'bold', fontSize: '1.1rem' }}>
                  ✈️ Crew Rostering
                </Typography>
              </Box>
              
              <List>
                {menuItems.map((item) => (
                  <ListItem key={item.index} disablePadding>
                    <ListItemButton
                      selected={activeView === item.index}
                      onClick={() => handleViewChange(item.index)}
                      sx={{
                        borderRadius: 1,
                        mb: 0.5,
                        '&.Mui-selected': {
                          backgroundColor: 'rgba(100, 181, 246, 0.2)',
                          '&:hover': {
                            backgroundColor: 'rgba(100, 181, 246, 0.3)',
                          },
                        },
                      }}
                    >
                      <ListItemIcon sx={{ color: activeView === item.index ? '#003DA5' : '#4D4D4D', minWidth: 36 }}>
                        {item.icon}
                      </ListItemIcon>
                      <ListItemText 
                        primary={item.text}
                        sx={{ 
                          '& .MuiListItemText-primary': {
                            color: activeView === item.index ? '#003DA5' : '#1A1A1A',
                            fontWeight: activeView === item.index ? 600 : 400,
                            fontSize: '0.9rem',
                          }
                        }}
                      />
                    </ListItemButton>
                  </ListItem>
                ))}
              </List>
            </Box>
          </Drawer>

          {/* Main Content */}
          <Box
            component="main"
            sx={{
              flexGrow: 1,
              transition: 'margin 0.3s ease-in-out',
              marginLeft: sidebarOpen ? 0 : 0,
              minHeight: '100vh',
              backgroundColor: '#E6F0FA',
            }}
          >
            {/* Top App Bar */}
            <AppBar 
              position="sticky" 
              sx={{ 
                backgroundColor: '#FFFFFF',
                borderBottom: '1px solid #F5F7FA',
                boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)',
                color: '#1A1A1A',
              }}
            >
              <Toolbar>
                <IconButton
                  color="inherit"
                  aria-label="toggle sidebar"
                  onClick={toggleSidebar}
                  edge="start"
                  sx={{ mr: 2 }}
                >
                  <MenuIcon />
                </IconButton>
                <Typography variant="h6" component="div" sx={{ flexGrow: 1, color: '#1A1A1A' }}>
                  {menuItems[activeView]?.text || 'Dashboard'}
                </Typography>
                {optimizationProgress && (
                  <Typography variant="body2" sx={{ color: '#4D4D4D' }}>
                    Status: {optimizationProgress.status} {optimizationProgress.progress ? `(${optimizationProgress.progress}%)` : ''}
                  </Typography>
                )}
              </Toolbar>
            </AppBar>

            {/* Content Area */}
            <Container maxWidth="xl" sx={{ mt: 3, mb: 3 }}>
              {renderContent()}
            </Container>
          </Box>
        </Box>

        <Snackbar
          open={notification.open}
          autoHideDuration={6000}
          onClose={handleCloseNotification}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        >
          <Alert 
            onClose={handleCloseNotification} 
            severity={notification.severity}
            sx={{ width: '100%' }}
          >
            {notification.message}
          </Alert>
        </Snackbar>

      </LocalizationProvider>
    </ThemeProvider>
  );
}

export default App;