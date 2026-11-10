export default {
  fetch(request, env) {
    return env.SYNC.fetch(request);
  },
};
