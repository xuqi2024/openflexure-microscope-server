describe("Smoke Test", () => {
  before(() => {
    cy.visit("/");
  });
  it("Renders the nav", () => {
    cy.get('[data-cy=nav-container]')
  });
});
