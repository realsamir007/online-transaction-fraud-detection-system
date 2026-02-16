import { createContext, useContext, useMemo, useReducer } from "react";
import type { Dispatch, ReactNode } from "react";
import type { Session } from "@supabase/supabase-js";
import type { AppRole } from "../types";

type State = {
  role: AppRole;
  session: Session | null;
  adminApiKey: string | null;
  sessionLoading: boolean;
};

type Action =
  | { type: "SET_SESSION_LOADING"; payload: boolean }
  | { type: "SET_USER_SESSION"; payload: Session | null }
  | { type: "SET_ADMIN_SESSION"; payload: string }
  | { type: "LOGOUT" };

const initialState: State = {
  role: "guest",
  session: null,
  adminApiKey: null,
  sessionLoading: true,
};

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "SET_SESSION_LOADING":
      return {
        ...state,
        sessionLoading: action.payload,
      };
    case "SET_USER_SESSION":
      return {
        ...state,
        role: action.payload ? "user" : "guest",
        session: action.payload,
        adminApiKey: null,
      };
    case "SET_ADMIN_SESSION":
      return {
        ...state,
        role: "admin",
        adminApiKey: action.payload,
        session: null,
        sessionLoading: false,
      };
    case "LOGOUT":
      return {
        ...state,
        role: "guest",
        session: null,
        adminApiKey: null,
        sessionLoading: false,
      };
    default:
      return state;
  }
}

type AppStateContextValue = {
  state: State;
  dispatch: Dispatch<Action>;
};

const AppStateContext = createContext<AppStateContextValue | undefined>(undefined);

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const value = useMemo(() => ({ state, dispatch }), [state]);

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}

export function useAppState() {
  const context = useContext(AppStateContext);
  if (!context) {
    throw new Error("useAppState must be used within AppStateProvider");
  }
  return context;
}
