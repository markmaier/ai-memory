import { combineReducers } from "redux";
import { layoutReducer } from "./reducers/layoutReducer";
import projectReducer from "./reducers/projectReducer";

const rootReducer = combineReducers({
  layout: layoutReducer,
  project: projectReducer,
});

export default rootReducer;
