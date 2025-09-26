import React, { useState, useRef, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  TextField,
  Button,
  IconButton,
  List,
  ListItem,
  ListItemText,
  Chip,
  Stack,
  Divider,
  CircularProgress,
  Alert,
} from '@mui/material';
import { Send, AddCircle, PlayArrow } from '@mui/icons-material';
import { apiService } from '../services/api';

const LLMDisruptionChat = ({ flights, crew, onParsed, onRunScenario, loading }) => {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      text: 'Describe a disruption in natural language. Examples:\n- "Captain C102 will not be able to fly tomorrow, he is sick."\n- "6E532 is delayed by 45 minutes."\n- "Cancel 6E210 from DEL to BOM."',
      parsed: null,
    },
  ]);
  const [parsing, setParsing] = useState(false);
  const listRef = useRef(null);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text) return;

    const userMsg = { role: 'user', text, parsed: null };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setParsing(true);

    try {
      const resp = await apiService.parseDisruptions(text);
      const data = resp?.data || {};
      const success = !!data.success;

      const fd = Array.isArray(data.flight_disruptions) ? data.flight_disruptions : [];
      const cs = Array.isArray(data.crew_sickness) ? data.crew_sickness : [];

      const assistantMsg = {
        role: 'assistant',
        text: success
          ? 'Parsed disruptions ready. You can add them to the Manual list or run a What-If scenario directly.'
          : `Failed to parse: ${data.error || 'Unknown error'}`,
        parsed: success
          ? {
              flight_disruptions: fd,
              crew_sickness: cs,
            }
          : null,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: `Error contacting parser: ${e?.message || e}`,
          parsed: null,
        },
      ]);
    } finally {
      setParsing(false);
    }
  };

  const handleAddToManual = (parsed) => {
    if (!parsed) return;
    onParsed?.(parsed);
  };

  const handleRunWhatIf = (parsed) => {
    if (!parsed) return;
    const body = {
      flight_disruptions: parsed.flight_disruptions || [],
      crew_sickness: parsed.crew_sickness || [],
    };
    onRunScenario?.(body);
  };

  const renderParsedChips = (parsed) => {
    if (!parsed) return null;
    const { flight_disruptions = [], crew_sickness = [] } = parsed;

    return (
      <Box sx={{ mt: 1 }}>
        {flight_disruptions.length > 0 && (
          <>
            <Typography variant="caption" color="text.secondary">
              Flight Disruptions
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ mt: 0.5 }}>
              {flight_disruptions.map((d, idx) => (
                <Chip
                  key={`fd-${idx}`}
                  color={d.type === 'cancellation' ? 'error' : 'warning'}
                  label={
                    d.type === 'cancellation'
                      ? `${d.flight_id} cancelled`
                      : `${d.flight_id} delayed ${d.delay_minutes || 0}m`
                  }
                  size="small"
                  sx={{ mb: 0.5 }}
                />
              ))}
            </Stack>
          </>
        )}
        {crew_sickness.length > 0 && (
          <>
            <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
              Crew Sickness
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ mt: 0.5 }}>
              {crew_sickness.map((s, idx) => (
                <Chip
                  key={`cs-${idx}`}
                  color="default"
                  label={`${s.crew_id} sick on ${s.sick_date}`}
                  size="small"
                  sx={{ mb: 0.5 }}
                />
              ))}
            </Stack>
          </>
        )}
        {flight_disruptions.length === 0 && crew_sickness.length === 0 && (
          <Typography variant="caption" color="text.secondary">
            No disruptions detected.
          </Typography>
        )}
      </Box>
    );
  };

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6" sx={{ color: '#1A1A1A', fontWeight: 600 }}>
            LLM Disruption Chat
          </Typography>
        </Box>

        <Alert severity="info" sx={{ mb: 2 }}>
          Type a natural-language instruction. The system will parse it into flight disruptions and crew sickness.
        </Alert>

        <Box
          ref={listRef}
          sx={{
            border: '1px solid #F0F0F0',
            borderRadius: 1,
            minHeight: 220,
            maxHeight: 320,
            overflowY: 'auto',
            backgroundColor: '#FAFAFA',
            p: 1,
            mb: 2,
          }}
        >
          <List dense disablePadding>
            {messages.map((m, i) => (
              <ListItem
                key={i}
                alignItems="flex-start"
                sx={{
                  backgroundColor: m.role === 'user' ? '#E8F0FE' : '#FFFFFF',
                  border: '1px solid #EEF2F7',
                  borderRadius: 1,
                  mb: 1,
                }}
              >
                <ListItemText
                  primary={
                    <Typography variant="caption" sx={{ fontWeight: 600 }}>
                      {m.role === 'user' ? 'You' : 'Assistant'}
                    </Typography>
                  }
                  secondary={
                    <>
                      <Typography
                        variant="body2"
                        sx={{ whiteSpace: 'pre-wrap', color: '#1A1A1A', mt: 0.5 }}
                      >
                        {m.text}
                      </Typography>
                      {m.parsed && (
                        <>
                          <Divider sx={{ my: 1 }} />
                          {renderParsedChips(m.parsed)}
                          <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                            <Button
                              variant="outlined"
                              startIcon={<AddCircle />}
                              size="small"
                              onClick={() => handleAddToManual(m.parsed)}
                              disabled={loading}
                            >
                              Add to Manual List
                            </Button>
                            <Button
                              variant="contained"
                              color="warning"
                              startIcon={<PlayArrow />}
                              size="small"
                              onClick={() => handleRunWhatIf(m.parsed)}
                              disabled={loading}
                            >
                              Run What-If
                            </Button>
                          </Stack>
                        </>
                      )}
                    </>
                  }
                />
              </ListItem>
            ))}
            {parsing && (
              <ListItem>
                <CircularProgress size={20} />
                <Typography variant="caption" sx={{ ml: 1 }}>
                  Parsing...
                </Typography>
              </ListItem>
            )}
          </List>
        </Box>

        <Box sx={{ display: 'flex', gap: 1 }}>
          <TextField
            placeholder='e.g., "6E210 is delayed by 30 minutes" or "C102 is sick on 2025-09-10"'
            value={input}
            onChange={(e) => setInput(e.target.value)}
            fullWidth
            size="small"
            multiline
            minRows={1}
            maxRows={4}
          />
          <IconButton color="primary" onClick={handleSend} disabled={parsing || !input.trim()}>
            <Send />
          </IconButton>
        </Box>
      </CardContent>
    </Card>
  );
};

export default LLMDisruptionChat;