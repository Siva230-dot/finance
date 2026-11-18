import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="grid min-h-screen place-items-center bg-bg px-6 text-center">
      <div>
        <p className="eyebrow">Folio 404</p>
        <h1 className="mt-3 font-serif text-6xl">This page is not in the ledger.</h1>
        <Link to="/" className="mt-8 inline-block text-gold hover:underline">Return home</Link>
      </div>
    </div>
  );
}
